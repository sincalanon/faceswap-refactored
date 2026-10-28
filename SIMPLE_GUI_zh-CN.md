# Faceswap 简易版界面（Web UI）使用说明

> **使用须知：** 请仅在获得所有相关人员明确同意的情况下使用其照片或视频，并遵守当地法律法规。禁止将本工具用于欺诈、骚扰、色情或侵犯他人权益的用途。

简易版界面是一个在浏览器里打开的中文向导，只保留最常用的参数，适合第一次使用 Faceswap 的用户。它**不修改**任何深度学习代码：每一步都是在后台调用 `faceswap.py extract / train / convert`（视频工具调用 `tools.py effmpeg`），并把日志、进度实时显示在页面上。需要全部参数时，仍然可以使用原版界面 `python faceswap.py gui` 或命令行。

## 安装

先按 [USAGE_zh-CN.md](USAGE_zh-CN.md) 装好 Faceswap 本身（`python setup.py`），然后在同一个环境里额外安装 Gradio：

```bash
pip install -r requirements/_requirements_simple_gui.txt
# 或者直接：pip install gradio
```

Gradio 是可选依赖，不安装也不影响原有的命令行和 Tk 图形界面。

## Windows 免安装版（NVIDIA 显卡）

不想装 Python 的 Windows 用户，可到仓库的 Releases 页面下载 `FaceswapSimple-win64-nvidia.7z.001`、`.002` 等全部分卷，放在同一文件夹，用 7-Zip 解压 `.7z.001`，然后双击 `FaceswapSimple.exe`，浏览器会自动打开本界面。

- 需要 NVIDIA RTX 20 系列或更新显卡，驱动 580 或更新版本；Python、PyTorch（CUDA 13）和全部依赖已内置。
- 黑色窗口是日志窗口，关闭它即退出程序。
- 常用模型权重已内置；如需下载其他模型而 GitHub 超时，可设置环境变量 `FACESWAP_GITHUB_MIRROR`（如 `https://ghfast.top/`）作为下载加速前缀。
- 可选参数：`FaceswapSimple.exe --port 8000`、`--no-browser`。
- 维护者发布新版：推送 `v*` 标签（如 `git tag v1.0.1 && git push origin v1.0.1`），或在 Actions 里手动运行 `build/windows-nvidia`，打包结果会自动上传到对应 Release。

## 启动

```bash
python app.py
```

然后在浏览器打开 <http://127.0.0.1:7860>。常用参数：

| 参数 | 作用 |
| --- | --- |
| `--port 8000` | 换一个端口 |
| `--host 0.0.0.0` | 允许同一局域网内的其他设备访问 |
| `--share` | 生成 Gradio 公网链接（拿到链接的人都能操作你的电脑，请谨慎） |
| `--inbrowser` | 启动后自动打开浏览器 |

## 三步上手

页面顶部先勾选「我已阅读并同意使用须知」，再选择**预设模式**：

- **新手模式**：轻量模型（lightweight）、批大小 8、视频每 5 帧提取一次，资源占用小、出结果快；
- **标准模式**：Faceswap 默认参数（Original 模型、批大小 16、每帧提取）。

切换预设会自动改写各页「高级设置」里的默认值，你也可以手动微调。

### ① 提取人脸

1. 「输入」填写一个图片文件夹或一个视频文件，例如 `D:\素材\张三.mp4`；
2. 「人脸输出文件夹」填写一个新文件夹，例如 `D:\faces\A`；
3. 点击「▶ 开始提取」。

A、B 两个人需要**分别**提取一次（得到 `faces\A` 和 `faces\B`）。提取时会在素材旁边生成对齐文件（`alignments.fsa` 或 `视频名_alignments.fsa`），第三步转换时会用到。首次运行需要联网下载检测模型。

### ② 训练模型

1. 「人脸 A 文件夹」选 `faces\A`（要被替换的人），「人脸 B 文件夹」选 `faces\B`（换上去的人）；
2. 「模型文件夹」填一个新建的空文件夹，例如 `D:\model`（选已有模型则继续训练）；
3. 点击「▶ 开始训练」。

每一边至少需要 25 张人脸，建议 500 - 5000 张。右侧「训练预览」会在每次保存模型时自动刷新（来自 `faceswap.py train -w` 写出的 `training_preview.png`）。觉得效果可以了就点「⏹ 停止」：训练会先保存模型再退出（可能需要一两分钟）。

### ③ 转换换脸

1. 「输入」填写**第一步提取过的同一份 A 素材**（图片文件夹或视频）；
2. 「输出文件夹」填写结果保存位置；
3. 「模型文件夹」选第二步的模型，点击「▶ 开始转换」。

输出格式默认为 auto：输入是视频就直接输出视频（ffmpeg），输入是图片就输出图片。

## 视频工具（可选）

「🎬 视频工具」页可以把视频拆成图片，或把图片序列合成为视频（可指定参考视频来沿用帧率并加入音频）。

## 其他功能

- 路径输入框会记住最近用过的路径和上次选择的预设，保存在用户配置目录下的 `faceswap-simple-gui/recent_paths.json`（Windows：`%APPDATA%`；macOS：`~/Library/Application Support`；Linux：`~/.config`；可用环境变量 `FACESWAP_SIMPLE_GUI_CONFIG_DIR` 修改）。
- 「高级设置」里的「批量模式」可一次提取一个父文件夹下的多个视频/图片文件夹。
- 右上角「🌓 深色/浅色」切换主题。
- 出错时页面会给出中文提示，例如：路径不存在、没检测到人脸、找不到模型、显卡/CUDA 不可用、缺少 ffmpeg、内存/显存不足等，完整日志在下方「运行日志」中。

## 常见问题

- **启动时提示未安装 Gradio**：执行 `pip install gradio`。
- **内存/显存不足**：在「高级设置」中减小批大小，或换用 lightweight 模型。
- **找不到 ffmpeg**：`pip install ffmpeg-binaries`，或安装系统 ffmpeg。
- **只想用 CPU**：可以运行，但训练会非常慢，建议先用新手模式试跑。
- 同一时间只能运行一个任务。关闭浏览器页面不会停止后台任务，请点「⏹ 停止」；在终端按 Ctrl+C 退出 `app.py` 时也会停止正在运行的任务（训练会尽量先保存模型）。
