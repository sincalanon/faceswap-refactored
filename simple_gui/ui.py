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
import typing as T

import gradio as gr

from . import commands
from .history import RecentPaths
from .paths import TRAINING_PREVIEW
from .presets import (ALIGNERS, COLOR_ADJUSTMENTS, DEFAULT_PRESET, DETECTORS, MASK_TYPES,
                      MASKERS, PRESETS, TRAINERS, WRITERS, get_preset)
from .runner import DONE, FAILED, STATUS_TEXT, STOPPED, JobRunner, Snapshot

POLL_SECONDS = 1.0

CONSENT_TEXT = ("**使用须知：** 请仅在获得所有相关人员明确同意的情况下使用其照片或视频，"
                "并遵守当地法律法规。禁止将本工具用于欺诈、骚扰、色情或侵犯他人权益的用途。")

INTRO = """# Faceswap 简易版
按顺序完成三步即可：**① 提取人脸** → **② 训练模型** → **③ 转换换脸**。
路径请填写本机上的完整路径（可直接粘贴），下拉框会记住最近用过的路径。
"""

CSS = """
.fs-bar {background: var(--block-border-color); border-radius: 6px; height: 14px;
         overflow: hidden;}
.fs-bar > div {background: var(--color-accent); height: 100%; transition: width .5s;}
.fs-progress-text {font-size: .9em; margin-top: 4px; opacity: .85;}
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


# Layout helpers
def _path_box(label: str, field: str, info: str = "") -> gr.Dropdown:
    """ A path input that is also a drop-down of recently used values """
    recent = HISTORY.get(field)
    return gr.Dropdown(choices=recent, value=recent[0] if recent else None, label=label,
                       info=info or None, allow_custom_value=True, interactive=True)


def _output_area(with_preview: bool = False) -> list[T.Any]:
    """ Status, progress, log (and preview) components shared by every tab """
    status = gr.Markdown("⏸️ **状态：空闲**")
    progress = gr.HTML(render_progress(RUNNER.snapshot()))
    outputs: list[T.Any] = [status, progress]
    if with_preview:
        with gr.Row():
            log = gr.Textbox(label="运行日志", lines=16, max_lines=16, autoscroll=True,
                             interactive=False, scale=1)
            preview = gr.Image(label="训练预览（每次保存模型时更新）", interactive=False,
                               type="pil", scale=1)
        return outputs + [log, preview]
    log = gr.Textbox(label="运行日志", lines=16, max_lines=16, autoscroll=True,
                     interactive=False)
    return outputs + [log]


def _buttons(start_label: str) -> tuple[gr.Button, gr.Button]:
    """ Start + stop buttons """
    with gr.Row():
        start = gr.Button(start_label, variant="primary")
        stop = gr.Button("⏹ 停止", variant="stop")
    return start, stop


def _wire(start: gr.Button, stop: gr.Button, func: T.Callable, inputs: list[T.Any],
          outputs: list[T.Any]) -> None:
    """ Connect a tab's buttons. The stop button writes into the status line. """
    start.click(func, inputs=inputs, outputs=outputs)
    stop.click(stop_job, inputs=None, outputs=outputs[0])


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


def _extract_tab(consent: gr.Checkbox, fields: _PresetFields, preset: str) -> None:
    """ ① 提取人脸 """
    vals = get_preset(preset, "extract")
    gr.Markdown("从照片文件夹或视频中找出人脸并裁剪保存。A、B 两个人需要**分别**提取一次。")
    input_path = _path_box("输入：图片文件夹或视频文件", "extract.input",
                           "例如 D:\\素材\\张三.mp4 或 /home/me/photos_a")
    output_dir = _path_box("人脸输出文件夹", "faces", "提取出的人脸保存到这里，供训练使用")
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
                1, 30, value=vals["extract_every_n"], step=1, label="视频每 N 帧提取一次"))
            min_size = fields.add("extract", "min_size", gr.Slider(
                0, 500, value=vals["min_size"], step=10, label="忽略小于此尺寸的人脸"))
        with gr.Row():
            skip_existing = fields.add("extract", "skip_existing", gr.Checkbox(
                value=vals["skip_existing"], label="跳过已处理过的帧"))
            batch_mode = gr.Checkbox(value=False,
                                     label="批量模式（输入为包含多个视频/文件夹的父目录）")
    start, stop = _buttons("▶ 开始提取")
    outputs = _output_area()
    _wire(start, stop, run_extract, [consent, input_path, output_dir, detector, aligner, masker,
                                     size, every_n, min_size, skip_existing, batch_mode],
          outputs)


def _train_tab(consent: gr.Checkbox, fields: _PresetFields, preset: str) -> None:
    """ ② 训练模型 """
    vals = get_preset(preset, "train")
    gr.Markdown("用 A、B 两个人的人脸训练换脸模型。训练时间越长效果越好，"
                "随时可以点击「停止」，模型会先保存再退出，之后可以继续训练。")
    with gr.Row():
        input_a = _path_box("人脸 A 文件夹（要被替换的人）", "faces")
        input_b = _path_box("人脸 B 文件夹（换上去的人）", "faces_b")
    model_dir = _path_box("模型文件夹", "model", "新建一个空文件夹，或选择已有模型以继续训练")
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
    start, stop = _buttons("▶ 开始训练")
    outputs = _output_area(with_preview=True)
    _wire(start, stop, run_train, [consent, input_a, input_b, model_dir, trainer, batch_size,
                                   iterations, save_interval, write_preview, warp, no_flip,
                                   no_color], outputs)


def _convert_tab(consent: gr.Checkbox, fields: _PresetFields, preset: str) -> None:
    """ ③ 转换换脸 """
    vals = get_preset(preset, "convert")
    gr.Markdown("用训练好的模型把原始素材里的 A 换成 B。输入必须是**做过「提取」的同一份素材**"
                "（提取时会在素材旁生成对齐文件 alignments）。")
    input_path = _path_box("输入：原始图片文件夹或视频（A 的素材）", "extract.input")
    output_dir = _path_box("输出文件夹", "convert.output")
    model_dir = _path_box("模型文件夹", "model")
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
    start, stop = _buttons("▶ 开始转换")
    outputs = _output_area()
    _wire(start, stop, run_convert, [consent, input_path, output_dir, model_dir, alignments,
                                     writer, color, mask_type, scale, swap], outputs)


def _video_tab(consent: gr.Checkbox) -> None:
    """ 视频工具 (effmpeg shortcuts) """
    gr.Markdown("可选工具：把视频拆成图片，或把（转换后的）图片序列合成视频。")
    action = gr.Radio(["视频 → 图片", "图片 → 视频"], value="视频 → 图片", label="操作")
    input_path = _path_box("输入（视频文件，或图片文件夹）", "video.input")
    output_path = _path_box("输出（图片文件夹，或视频文件如 out.mp4）", "video.output")
    with gr.Accordion("合成视频选项", open=False):
        reference = gr.Textbox(label="参考视频（用于帧率和音频，可留空）")
        with gr.Row():
            mux_audio = gr.Checkbox(value=False, label="加入参考视频的音频")
            fps = gr.Number(value=25, label="帧率（没有参考视频时使用）")
    start, stop = _buttons("▶ 开始")
    outputs = _output_area()
    _wire(start, stop, run_video, [consent, action, input_path, output_path, reference,
                                   mux_audio, fps], outputs)


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
            dark = gr.Button("🌓 深色/浅色", size="sm", scale=0)
        gr.Markdown(CONSENT_TEXT)
        consent = gr.Checkbox(value=HISTORY.last("consent") == "yes",
                              label="我已阅读并同意使用须知")
        mode = gr.Radio(list(PRESETS), value=preset, label="预设模式",
                        info=("新手模式：轻量模型、视频抽帧，快速出结果；"
                              "标准模式：Faceswap 默认参数"))
        with gr.Tabs():
            with gr.Tab("① 提取人脸"):
                _extract_tab(consent, fields, preset)
            with gr.Tab("② 训练模型"):
                _train_tab(consent, fields, preset)
            with gr.Tab("③ 转换换脸"):
                _convert_tab(consent, fields, preset)
            with gr.Tab("🎬 视频工具"):
                _video_tab(consent)
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
