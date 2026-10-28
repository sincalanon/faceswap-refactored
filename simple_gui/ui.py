#!/usr/bin/env python3
""" The Gradio web UI for the simple GUI (简易版图形界面).

Three steps (提取 → 训练 → 转换) plus a video helper. Each "开始" button builds a command with
:mod:`simple_gui.commands`, runs it with :class:`simple_gui.runner.JobRunner` and streams the
log, progress and (for training) the preview image back to the page.
"""
from __future__ import annotations

import atexit
import html
import inspect
import os
import subprocess
import sys
import typing as T

import gradio as gr

from . import commands, workspace
from .history import RecentPaths
from .paths import (IMAGE_EXTENSIONS, TRAINING_PREVIEW, clean_path, count_images, has_model,
                    is_video)
from .presets import (ALIGNERS, COLOR_ADJUSTMENTS, DEFAULT_PRESET, DETECTORS, MASK_TYPES,
                      MASKERS, PRESETS, TRAINERS, WRITERS, get_preset)
from .runner import DONE, FAILED, STATUS_TEXT, STOPPED, JobRunner, Snapshot

POLL_SECONDS = 1.0

CONSENT_TEXT = ("**使用须知：** 请仅在获得所有相关人员明确同意的情况下使用其照片或视频，"
                "并遵守当地法律法规。禁止将本工具用于欺诈、骚扰、色情或侵犯他人权益的用途。")

INTRO = """# 🎭 Faceswap 简易版
按顺序完成三步：**① 提取人脸** → **② 训练模型** → **③ 转换换脸**。先填一次「工作文件夹」，所有路径自动填好。
"""

WORKDIR_HELP = """按下「应用」后会在工作文件夹里建好这些子文件夹，**把素材放进去即可**：
`A`（A 的素材：1 个视频或若干照片）· `B`（B 的素材）· `facesA` / `facesB`（提取出的人脸）·
`model`（模型）· `output`（换脸结果）· `frames`（视频工具拆出的图片）"""

VIDEO_TO_IMAGES = "视频 → 图片"
IMAGES_TO_VIDEO = "图片 → 视频"

CSS = """
.fs-bar {background: var(--block-border-color); border-radius: 6px; height: 14px;
         overflow: hidden;}
.fs-bar > div {background: var(--color-accent); height: 100%; transition: width .5s;}
.fs-progress-text {font-size: .9em; margin-top: 4px; opacity: .85;}
.gradio-container {max-width: 1280px !important; margin: 0 auto !important;}
.fs-consent {font-size: .85em; opacity: .8;}
.fs-dash table {width: 100%; text-align: center;}
.fs-dash td, .fs-dash th {padding: 4px 6px !important;}
button[role="tab"] {font-size: 1.05em !important; font-weight: 600 !important;}
"""

DARK_TOGGLE_JS = "() => { document.body.classList.toggle('dark'); }"

RUNNER = JobRunner()
HISTORY = RecentPaths()

UpdateTuple = tuple[T.Any, ...]


# Rendering helpers
def render_progress(snap: Snapshot) -> str:
    """ HTML progress bar for a snapshot """
    fraction = snap.progress.fraction
    if fraction is None:
        width, pct = (100 if snap.running else 0), ""
    else:
        width, pct = int(round(fraction * 100)), f"{fraction * 100:.0f}%  "
    text = html.escape(snap.progress.text or "")
    return (f"<div class='fs-bar'><div style='width:{width}%'></div></div>"
            f"<div class='fs-progress-text'>{pct}{text}</div>")


def render_status(snap: Snapshot) -> str:
    """ Markdown status line, including the friendly error message when there is one """
    icons = {DONE: "✅", FAILED: "❌", STOPPED: "⏹️"}
    line = f"{icons.get(snap.status, '⏳')} **状态：{STATUS_TEXT.get(snap.status, snap.status)}**"
    if snap.message:
        line += f"\n\n{'⚠️ ' if snap.status == DONE else ''}{snap.message}"
    return line


def _command_line(command: list[str]) -> str:
    """ Display version of the command (``python faceswap.py ...``) """
    parts = ["python"] + command[2:]
    return "$ " + " ".join(f'"{part}"' if " " in part else part for part in parts)


def _render_log(snap: Snapshot) -> str:
    """ Log text with the command line on top """
    return f"{_command_line(snap.command)}\n{snap.log}" if snap.command else snap.log


def _message(text: str) -> tuple[str, str, str]:
    """ Outputs for a job that could not start """
    return f"❌ **无法开始**\n\n{text}", "", ""


# Job streaming
def _stream(opts: commands.JobOptions,
            consent: bool,
            remember: dict[str, str],
            with_preview: bool = False) -> T.Iterator[UpdateTuple]:
    """ Validate, launch and stream a job. Yields (status, progress, log[, preview]). """
    extra: UpdateTuple = (gr.update(),) if with_preview else ()
    errors = _preflight(opts, consent)
    if errors:
        yield _message("\n".join(f"- {err}" for err in errors)) + extra
        return
    HISTORY.add_many(remember)
    if with_preview and os.path.exists(TRAINING_PREVIEW):
        os.remove(TRAINING_PREVIEW)  # Don't show a stale preview from an older session
    try:
        started = RUNNER.start(commands.build_command(opts), opts.command,
                               iterations=getattr(opts, "iterations", None))
    except OSError as err:
        yield _message(f"启动进程失败：{err}") + extra
        return
    if not started:
        yield _message("已有任务正在运行。请等待它完成，或先点击「停止」。") + extra
        return
    yield from _poll(with_preview)


def _preflight(opts: commands.JobOptions, consent: bool) -> list[str]:
    """ Consent + path validation """
    if not consent:
        return ["请先勾选页面顶部的「我已阅读并同意使用须知」。"]
    return commands.validate(opts)


def _poll(with_preview: bool) -> T.Iterator[UpdateTuple]:
    """ Yield the job state every :data:`POLL_SECONDS` until it ends """
    preview_mtime = 0.0
    while True:
        snap = RUNNER.snapshot()
        out: UpdateTuple = (render_status(snap), render_progress(snap), _render_log(snap))
        if with_preview:
            preview, preview_mtime = _preview_update(preview_mtime)
            out += (preview,)
        yield out
        if not snap.running:
            return
        RUNNER.wait(POLL_SECONDS)


def _preview_update(last_mtime: float) -> tuple[T.Any, float]:
    """ Load the trainer's preview image if it changed since ``last_mtime`` """
    try:
        mtime = os.path.getmtime(TRAINING_PREVIEW)
    except OSError:
        return gr.update(), last_mtime
    if mtime <= last_mtime:
        return gr.update(), last_mtime
    try:
        from PIL import Image  # pylint:disable=import-outside-toplevel
        with Image.open(TRAINING_PREVIEW) as img:
            return img.convert("RGB"), mtime
    except (OSError, ValueError):  # Half written file: try again next poll
        return gr.update(), last_mtime


def stop_job() -> str:
    """ Stop button handler """
    if RUNNER.stop():
        return "⏹️ 已发送停止请求。训练会先保存模型再退出，可能需要一两分钟。"
    return "当前没有正在运行的任务。"


# Event handlers (one per tab). Positional arguments follow the component order in the UI.
def run_extract(consent: bool, input_path: str, output_dir: str, detector: str, aligner: str,
                masker: str, size: float, every_n: float, min_size: float, skip_existing: bool,
                batch_mode: bool) -> T.Iterator[UpdateTuple]:
    """ 开始提取 """
    opts = commands.ExtractOptions(input_path, output_dir, detector, aligner, masker, int(size),
                                   int(every_n), int(min_size), skip_existing, batch_mode)
    yield from _stream(opts, consent, {"extract.input": input_path,
                                       "faces": output_dir})


def run_train(consent: bool, input_a: str, input_b: str, model_dir: str, trainer: str,
              batch_size: float, iterations: float, save_interval: float, write_preview: bool,
              warp_to_landmarks: bool, no_flip: bool,
              no_augment_color: bool) -> T.Iterator[UpdateTuple]:
    """ 开始训练 """
    opts = commands.TrainOptions(input_a, input_b, model_dir, trainer, int(batch_size),
                                 int(iterations), int(save_interval), write_preview,
                                 warp_to_landmarks, no_flip, no_augment_color)
    yield from _stream(opts, consent, {"faces": input_a, "faces_b": input_b,
                                       "model": model_dir}, with_preview=True)


def run_convert(consent: bool, input_path: str, output_dir: str, model_dir: str,
                alignments: str, writer: str, color: str, mask_type: str, scale: float,
                swap_model: bool) -> T.Iterator[UpdateTuple]:
    """ 开始转换 """
    opts = commands.ConvertOptions(input_path, output_dir, model_dir, alignments, writer, color,
                                   mask_type, int(scale), swap_model)
    yield from _stream(opts, consent, {"extract.input": input_path,
                                       "convert.output": output_dir, "model": model_dir})


def run_video(consent: bool, action_label: str, input_path: str, output_path: str,
              reference: str, mux_audio: bool, fps: float) -> T.Iterator[UpdateTuple]:
    """ 视频工具 """
    action = "extract" if action_label.startswith("视频") else "gen-vid"
    opts = commands.VideoOptions(action, input_path, output_path, reference, mux_audio,
                                 float(fps))
    yield from _stream(opts, consent, {"video.input": input_path, "video.output": output_path})


# Progress dashboard
def _describe_source(folder: str) -> str:
    """ What a material folder (A or B) holds, for the dashboard """
    if not os.path.isdir(folder):
        return "⬜ 未放"
    names = os.listdir(folder)
    videos = [name for name in names if is_video(name)]
    images = count_images(folder)
    if images:
        return f"✅ {images} 张照片"
    if len(videos) == 1:
        return "✅ 1 个视频"
    if videos:
        return f"⚠️ {len(videos)} 个视频"
    return "⬜ 未放"


def _count_results(folder: str) -> int:
    """ Number of converted images or videos in the output folder """
    if not os.path.isdir(folder):
        return 0
    return sum(1 for name in os.listdir(folder)
               if is_video(name) or os.path.splitext(name)[-1].lower() in IMAGE_EXTENSIONS)


def render_dashboard(workdir: str | None) -> str:
    """ A one row table of where the user is in the workflow, plus the next thing to do """
    paths = workspace.layout(workdir or HISTORY.workdir)
    if not paths or not os.path.isdir(clean_path(workdir or HISTORY.workdir)):
        return WORKDIR_HELP
    faces_a, faces_b = count_images(paths["faces_a"]), count_images(paths["faces_b"])
    src_a, src_b = _describe_source(paths["src_a"]), _describe_source(paths["src_b"])
    model = has_model(paths["model"])
    results = _count_results(paths["output"])
    if not src_a.startswith("✅") or not src_b.startswith("✅"):
        tip = "把 A 的视频/照片放进 `A` 文件夹，B 的放进 `B` 文件夹，然后点「🔄 刷新」。"
    elif faces_a == 0:
        tip = "去「① 提取人脸」点「填入 A 的路径」→「开始提取」。"
    elif faces_b == 0:
        tip = "去「① 提取人脸」点「填入 B 的路径」→「开始提取」。"
    elif min(faces_a, faces_b) < commands.MIN_TRAIN_IMAGES:
        tip = f"人脸太少（每边至少 {commands.MIN_TRAIN_IMAGES} 张），请换更长更清楚的素材再提取。"
    elif not model:
        tip = "先删掉 facesA / facesB 里的错脸和模糊脸，再去「② 训练模型」点「开始训练」。"
    elif not results:
        tip = "预览满意后停止训练，去「③ 转换换脸」点「开始转换」。"
    else:
        tip = "🎉 已生成成品，点「③ 转换换脸」里的「📂 打开输出文件夹」查看。"

    def faces(num: int) -> str:
        return f"✅ {num} 张" if num else "⬜ 0 张"

    return ("| A 素材 | B 素材 | A 人脸 | B 人脸 | 模型 | 成品 |\n|---|---|---|---|---|---|\n"
            f"| {src_a} | {src_b} | {faces(faces_a)} | {faces(faces_b)} | "
            f"{'✅ 已训练' if model else '⬜ 未训练'} | {'✅ ' if results else '⬜ '}{results} 个 |"
            f"\n\n**下一步：** {tip}")


def open_folder(path: str | None) -> str:
    """ Open a folder (or the folder of a file) in the system file manager """
    path = clean_path(path)
    if path and not os.path.isdir(path):
        path = os.path.dirname(path)
    if not path or not os.path.isdir(path):
        return "❌ **文件夹还不存在**：请先填写路径，或先运行这一步。"
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)  # type:ignore[attr-defined]  # pylint:disable=no-member
        else:
            subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", path])
    except OSError as err:
        return f"❌ 无法打开文件夹：{err}"
    return f"📂 已打开：`{path}`"


# Layout helpers
# Which layout entry fills each path box when a work folder is set
BOX_DEFAULTS = {"extract.input": "src_a", "extract.output": "faces_a", "train.a": "faces_a",
                "train.b": "faces_b", "train.model": "model", "convert.input": "src_a",
                "convert.output": "output", "convert.model": "model", "video.input": "src_a",
                "video.output": "frames"}
VIDEO_DEFAULTS = {VIDEO_TO_IMAGES: ("src_a", "frames"), IMAGES_TO_VIDEO: ("output", "result")}
PATH_BOXES: dict[str, gr.Dropdown] = {}


def _path_update(field: str, value: str) -> T.Any:
    """ Dropdown update that shows ``value`` and keeps the recent values as choices """
    choices = [value] + [val for val in HISTORY.get(field) if val != value]
    return gr.update(choices=choices, value=value)


def _path_box(label: str, field: str, info: str = "", box: str = "") -> gr.Dropdown:
    """ A path input that is also a drop-down of recently used values. When a work folder is
    set, its layout path for ``box`` is the starting value. """
    recent = HISTORY.get(field)
    value = workspace.layout(HISTORY.workdir).get(BOX_DEFAULTS.get(box, ""), "")
    if value:
        recent = [value] + [val for val in recent if val != value]
    component = gr.Dropdown(choices=recent, value=recent[0] if recent else None, label=label,
                            info=info or None, allow_custom_value=True, interactive=True)
    if box:
        PATH_BOXES[box] = component
    return component


def _fields_for(box: str) -> str:
    """ The history field a path box remembers its values under """
    return {"extract.input": "extract.input", "extract.output": "faces", "train.a": "faces",
            "train.b": "faces_b", "train.model": "model", "convert.input": "extract.input",
            "convert.output": "convert.output", "convert.model": "model",
            "video.input": "video.input", "video.output": "video.output"}[box]


def apply_workdir(workdir: str, video_action: str) -> list[T.Any]:
    """ Create and remember the work folder, then fill every path box from its layout """
    errors = workspace.create(workdir)
    if errors:
        return [f"❌ {errors[0]}"] + [gr.update() for _ in PATH_BOXES]
    HISTORY.workdir = workdir
    paths = workspace.layout(workdir)
    values = {box: paths[key] for box, key in BOX_DEFAULTS.items()}
    values["video.input"], values["video.output"] = (
        paths[key] for key in VIDEO_DEFAULTS.get(video_action, VIDEO_DEFAULTS[VIDEO_TO_IMAGES]))
    status = f"✅ 已应用 `{clean_path(workdir)}`，所有路径已填好，下次打开自动沿用。"
    return [status] + [_path_update(_fields_for(box), values[box]) for box in PATH_BOXES]


def fill_extract(workdir: str, person: str) -> list[T.Any]:
    """ Fill the extract input/output with the A or B layout paths """
    paths = workspace.layout(workdir or HISTORY.workdir)
    if not paths:
        return [gr.update(), gr.update()]
    key = person.lower()
    return [_path_update("extract.input", paths[f"src_{key}"]),
            _path_update("faces", paths[f"faces_{key}"])]


def fill_video(workdir: str, action_label: str) -> list[T.Any]:
    """ Switch the video tool paths when the action changes (only with a work folder) """
    paths = workspace.layout(workdir or HISTORY.workdir)
    if not paths:
        return [gr.update(), gr.update()]
    src, dst = VIDEO_DEFAULTS.get(action_label, VIDEO_DEFAULTS[VIDEO_TO_IMAGES])
    return [_path_update("video.input", paths[src]), _path_update("video.output", paths[dst])]


def _output_area(with_preview: bool = False) -> list[T.Any]:
    """ Status, progress, log (and preview) components shared by every tab """
    status = gr.Markdown("⏸️ **状态：空闲**")
    progress = gr.HTML(render_progress(RUNNER.snapshot()))
    outputs: list[T.Any] = [status, progress]
    if with_preview:
        with gr.Row():
            log = gr.Textbox(label="运行日志（出错时请截图这里）", lines=16, max_lines=16,
                             autoscroll=True, interactive=False, scale=1)
            preview = gr.Image(label="训练预览（每次保存模型时更新）", interactive=False,
                               type="pil", scale=1)
        return outputs + [log, preview]
    log = gr.Textbox(label="运行日志（出错时请截图这里）", lines=12, max_lines=12,
                     autoscroll=True, interactive=False)
    return outputs + [log]


def _buttons(start_label: str) -> tuple[gr.Button, gr.Button, gr.Button]:
    """ Start, stop and "open output folder" buttons """
    with gr.Row():
        start = gr.Button(start_label, variant="primary", scale=3)
        stop = gr.Button("⏹ 停止", variant="stop", scale=1)
        opener = gr.Button("📂 打开输出文件夹", scale=1)
    return start, stop, opener


JOB_EVENTS: list[T.Any] = []
""" The start events of every tab, so the dashboard can refresh when a job ends """


def _wire(start: gr.Button, stop: gr.Button, func: T.Callable, inputs: list[T.Any],
          outputs: list[T.Any], opener: tuple[gr.Button, gr.Dropdown]) -> None:
    """ Connect a tab's buttons. The stop button writes into the status line and the open
    button opens the folder currently in the given path box. """
    JOB_EVENTS.append(start.click(func, inputs=inputs, outputs=outputs))
    stop.click(stop_job, inputs=None, outputs=outputs[0])
    opener[0].click(open_folder, inputs=opener[1], outputs=outputs[0])


class _PresetFields:
    """ Collects the components a preset controls so the preset selector can update them """
    def __init__(self) -> None:
        self.items: list[tuple[str, str, T.Any]] = []

    def add(self, section: str, key: str, component: T.Any) -> T.Any:
        """ Register a component and return it """
        self.items.append((section, key, component))
        return component

    @property
    def components(self) -> list[T.Any]:
        """ The registered components in order """
        return [item[2] for item in self.items]

    def values(self, preset: str) -> list[T.Any]:
        """ The preset's value for each registered component """
        return [get_preset(preset, section)[key] for section, key, _ in self.items]


def _extract_tab(consent: gr.Checkbox, fields: _PresetFields, preset: str,
                 workdir: gr.Textbox) -> None:
    """ ① 提取人脸 """
    vals = get_preset(preset, "extract")
    gr.Markdown("从照片文件夹或视频中找出人脸并裁剪保存。A、B 两个人需要**分别**提取一次："
                "先点「填入 A」提取一次，完成后点「填入 B」再提取一次。")
    with gr.Row():
        fill_a = gr.Button("👤 填入 A 的路径", size="sm")
        fill_b = gr.Button("👤 填入 B 的路径", size="sm")
    input_path = _path_box("输入：图片文件夹或视频文件", "extract.input",
                           "例如 D:\\fs\\A（文件夹里只有一个视频时会自动使用它）",
                           box="extract.input")
    output_dir = _path_box("人脸输出文件夹", "faces", "提取出的人脸保存到这里，供训练使用",
                           box="extract.output")
    fill_a.click(lambda wd: fill_extract(wd, "A"), inputs=workdir,
                 outputs=[input_path, output_dir])
    fill_b.click(lambda wd: fill_extract(wd, "B"), inputs=workdir,
                 outputs=[input_path, output_dir])
    with gr.Accordion("高级设置（一般无需修改）", open=False):
        with gr.Row():
            detector = fields.add("extract", "detector", gr.Dropdown(
                DETECTORS, value=vals["detector"], label="人脸检测器",
                info="auto = 按 CPU/GPU 自动选择"))
            aligner = fields.add("extract", "aligner", gr.Dropdown(
                ALIGNERS, value=vals["aligner"], label="关键点对齐器"))
            masker = fields.add("extract", "masker", gr.Dropdown(
                MASKERS, value=vals["masker"], label="额外遮罩", info="none = 只用默认遮罩"))
        with gr.Row():
            size = fields.add("extract", "size", gr.Slider(
                256, 1024, value=vals["size"], step=64, label="人脸图片尺寸（像素）"))
            every_n = fields.add("extract", "extract_every_n", gr.Slider(
                1, 30, value=vals["extract_every_n"], step=1, label="视频每 N 帧提取一次（只对视频生效，图片文件夹会处理全部图片）"))
            min_size = fields.add("extract", "min_size", gr.Slider(
                0, 500, value=vals["min_size"], step=10, label="忽略小于此尺寸的人脸"))
        with gr.Row():
            skip_existing = fields.add("extract", "skip_existing", gr.Checkbox(
                value=vals["skip_existing"], label="跳过已处理过的帧"))
            batch_mode = gr.Checkbox(value=False,
                                     label="批量模式（输入为包含多个视频/文件夹的父目录）")
    start, stop, open_btn = _buttons("▶ 开始提取")
    outputs = _output_area()
    _wire(start, stop, run_extract, [consent, input_path, output_dir, detector, aligner, masker,
                                     size, every_n, min_size, skip_existing, batch_mode],
          outputs, opener=(open_btn, output_dir))


def _train_tab(consent: gr.Checkbox, fields: _PresetFields, preset: str) -> None:
    """ ② 训练模型 """
    vals = get_preset(preset, "train")
    gr.Markdown("用 A、B 两个人的人脸训练换脸模型。训练时间越长效果越好，"
                "随时可以点击「停止」，模型会先保存再退出，之后可以继续训练。")
    with gr.Row():
        input_a = _path_box("人脸 A 文件夹（要被替换的人）", "faces", box="train.a")
        input_b = _path_box("人脸 B 文件夹（换上去的人）", "faces_b", box="train.b")
    model_dir = _path_box("模型文件夹", "model",
                          "训练出的换脸模型保存在这里：第一次填一个空文件夹，继续训练填同一个",
                          box="train.model")
    with gr.Accordion("高级设置（一般无需修改）", open=False):
        with gr.Row():
            trainer = fields.add("train", "trainer", gr.Dropdown(
                TRAINERS, value=vals["trainer"], label="模型类型",
                info="lightweight 最省资源；original 为默认"))
            batch_size = fields.add("train", "batch_size", gr.Slider(
                1, 64, value=vals["batch_size"], step=1, label="批大小（显存不足时调小）"))
        with gr.Row():
            iterations = fields.add("train", "iterations", gr.Number(
                value=vals["iterations"], precision=0, label="迭代次数上限"))
            save_interval = fields.add("train", "save_interval", gr.Slider(
                10, 2000, value=vals["save_interval"], step=10, label="每 N 次迭代保存一次"))
        with gr.Row():
            write_preview = fields.add("train", "write_preview", gr.Checkbox(
                value=vals["write_preview"], label="生成训练预览图"))
            warp = fields.add("train", "warp_to_landmarks", gr.Checkbox(
                value=vals["warp_to_landmarks"], label="按关键点变形（Warp to landmarks）"))
            no_flip = fields.add("train", "no_flip", gr.Checkbox(
                value=vals["no_flip"], label="关闭随机翻转"))
            no_color = fields.add("train", "no_augment_color", gr.Checkbox(
                value=vals["no_augment_color"], label="关闭颜色增强"))
    start, stop, open_btn = _buttons("▶ 开始训练")
    outputs = _output_area(with_preview=True)
    _wire(start, stop, run_train, [consent, input_a, input_b, model_dir, trainer, batch_size,
                                   iterations, save_interval, write_preview, warp, no_flip,
                                   no_color], outputs, opener=(open_btn, model_dir))


def _convert_tab(consent: gr.Checkbox, fields: _PresetFields, preset: str) -> None:
    """ ③ 转换换脸 """
    vals = get_preset(preset, "convert")
    gr.Markdown("用训练好的模型把原始素材里的 A 换成 B。输入必须是**做过「提取」的同一份素材**"
                "（提取时会在素材旁生成对齐文件 alignments）。")
    input_path = _path_box("输入：原始图片文件夹或视频（A 的素材）", "extract.input",
                           box="convert.input")
    output_dir = _path_box("输出文件夹", "convert.output", box="convert.output")
    model_dir = _path_box("模型文件夹", "model", box="convert.model")
    with gr.Accordion("高级设置（一般无需修改）", open=False):
        alignments = gr.Textbox(label="对齐文件路径（留空 = 自动查找）")
        with gr.Row():
            writer = fields.add("convert", "writer", gr.Dropdown(
                WRITERS, value=vals["writer"], label="输出格式",
                info="auto：视频输入→ffmpeg 视频；图片输入→opencv 图片"))
            color = fields.add("convert", "color_adjustment", gr.Dropdown(
                COLOR_ADJUSTMENTS, value=vals["color_adjustment"], label="颜色调整"))
            mask_type = fields.add("convert", "mask_type", gr.Dropdown(
                MASK_TYPES, value=vals["mask_type"], label="遮罩类型"))
        with gr.Row():
            scale = fields.add("convert", "output_scale", gr.Slider(
                25, 400, value=vals["output_scale"], step=25, label="输出缩放（%）"))
            swap = fields.add("convert", "swap_model", gr.Checkbox(
                value=vals["swap_model"], label="反向转换（B → A）"))
    start, stop, open_btn = _buttons("▶ 开始转换")
    outputs = _output_area()
    _wire(start, stop, run_convert, [consent, input_path, output_dir, model_dir, alignments,
                                     writer, color, mask_type, scale, swap], outputs,
          opener=(open_btn, output_dir))


def _video_tab(consent: gr.Checkbox, workdir: gr.Textbox) -> gr.Radio:
    """ 视频工具 (effmpeg shortcuts) """
    gr.Markdown("可选工具：把视频拆成图片，或把（转换后的）图片序列合成视频。")
    action = gr.Radio([VIDEO_TO_IMAGES, IMAGES_TO_VIDEO], value=VIDEO_TO_IMAGES, label="操作")
    input_path = _path_box("输入（视频文件，或图片文件夹）", "video.input", box="video.input")
    output_path = _path_box("输出（图片文件夹，或视频文件如 out.mp4）", "video.output",
                            box="video.output")
    action.change(fill_video, inputs=[workdir, action], outputs=[input_path, output_path])
    with gr.Accordion("合成视频选项", open=False):
        reference = gr.Textbox(label="参考视频（用于帧率和音频，可留空）")
        with gr.Row():
            mux_audio = gr.Checkbox(value=False, label="加入参考视频的音频")
            fps = gr.Number(value=25, label="帧率（没有参考视频时使用）")
    start, stop, open_btn = _buttons("▶ 开始")
    outputs = _output_area()
    _wire(start, stop, run_video, [consent, action, input_path, output_path, reference,
                                   mux_audio, fps], outputs, opener=(open_btn, output_path))
    return action


def _on_preset(name: str, fields: _PresetFields) -> list[T.Any]:
    """ Remember the preset and return the new values for its fields """
    HISTORY.preset = name
    return fields.values(name)


def _on_consent(value: bool) -> None:
    """ Remember that the notice was accepted so it is pre-ticked next time """
    HISTORY.add_many({"consent": "yes" if value else ""})


def build_app() -> gr.Blocks:
    """ Build the Gradio Blocks app """
    preset = HISTORY.preset if HISTORY.preset in PRESETS else DEFAULT_PRESET
    fields = _PresetFields()
    with gr.Blocks(title="Faceswap 简易版", **_blocks_style_kwargs()) as app:
        with gr.Row():
            gr.Markdown(INTRO)
            dark = gr.Button("🌓 深色/浅色", size="sm", scale=0, min_width=120)
        with gr.Row(equal_height=True):
            with gr.Column(scale=3):
                gr.Markdown(CONSENT_TEXT, elem_classes="fs-consent")
                consent = gr.Checkbox(value=HISTORY.last("consent") == "yes",
                                      label="我已阅读并同意使用须知")
            mode = gr.Radio(list(PRESETS), value=preset, label="预设模式", scale=2,
                            info="新手模式：轻量模型、快速出结果；标准模式：Faceswap 默认参数")
        with gr.Group():
            with gr.Row(equal_height=True):
                workdir = gr.Textbox(value=HISTORY.workdir, label="📁 工作文件夹（填一次即可）",
                                     placeholder="例如 D:\\fs 或 C:\\Users\\你的用户名\\Desktop\\fmx",
                                     scale=4)
                apply = gr.Button("✔ 应用（自动填好路径）", variant="primary", scale=0, min_width=220)
                refresh = gr.Button("🔄 刷新进度", scale=0, min_width=140)
                open_work = gr.Button("📂 打开文件夹", scale=0, min_width=140)
            workdir_status = gr.Markdown("")
            dashboard = gr.Markdown(render_dashboard(HISTORY.workdir), elem_classes="fs-dash")
        PATH_BOXES.clear()
        JOB_EVENTS.clear()
        with gr.Tabs():
            with gr.Tab("① 提取人脸"):
                _extract_tab(consent, fields, preset, workdir)
            with gr.Tab("② 训练模型"):
                _train_tab(consent, fields, preset)
            with gr.Tab("③ 转换换脸"):
                _convert_tab(consent, fields, preset)
            with gr.Tab("🎬 视频工具"):
                video_action = _video_tab(consent, workdir)
        apply.click(apply_workdir, inputs=[workdir, video_action],
                    outputs=[workdir_status] + list(PATH_BOXES.values())).then(
                        render_dashboard, inputs=workdir, outputs=dashboard)
        refresh.click(render_dashboard, inputs=workdir, outputs=dashboard)
        open_work.click(open_folder, inputs=workdir, outputs=workdir_status)
        for event in JOB_EVENTS:
            event.then(render_dashboard, inputs=workdir, outputs=dashboard)
        app.load(render_dashboard, inputs=workdir, outputs=dashboard)
        mode.change(lambda name: _on_preset(name, fields), inputs=mode,
                    outputs=fields.components)
        consent.change(_on_consent, inputs=consent, outputs=None)
        dark.click(None, js=DARK_TOGGLE_JS)
    return app


def _style() -> dict[str, T.Any]:
    """ Theme and CSS """
    return {"theme": gr.themes.Soft(), "css": CSS}


def _style_goes_to_launch() -> bool:
    """ Gradio 6 moved ``theme``/``css`` from ``Blocks()`` to ``launch()`` """
    return "theme" in inspect.signature(gr.Blocks.launch).parameters


def _blocks_style_kwargs() -> dict[str, T.Any]:
    """ Style arguments for ``gr.Blocks`` (Gradio < 6) """
    return {} if _style_goes_to_launch() else _style()


def _bypass_proxy_for_localhost() -> None:
    """ Gradio checks that it can reach itself on start up. A system HTTP proxy (common on
    machines that use one for downloads) would intercept that request and make the launch fail,
    so local addresses are excluded from proxying for this process. """
    for var in ("NO_PROXY", "no_proxy"):
        current = [item for item in os.environ.get(var, "").split(",") if item]
        missing = [host for host in ("127.0.0.1", "localhost", "0.0.0.0") if host not in current]
        os.environ[var] = ",".join(current + missing)


def launch(host: str = "127.0.0.1", port: int = 7860, share: bool = False,
           inbrowser: bool = False) -> None:
    """ Build and serve the app (blocks until stopped) """
    _bypass_proxy_for_localhost()
    atexit.register(RUNNER.shutdown)
    app = build_app()
    kwargs: dict[str, T.Any] = {"server_name": host, "server_port": port, "share": share,
                                "inbrowser": inbrowser}
    if _style_goes_to_launch():
        kwargs.update(_style())
    app.queue().launch(**kwargs)
