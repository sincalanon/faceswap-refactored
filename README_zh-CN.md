# faceswap 重构版（faceswap-refactored）

本仓库基于 [deepfakes/faceswap](https://github.com/deepfakes/faceswap)（上游 `master` @ `f530cb7`），在**不改变正常功能**的前提下做了代码重构、静态检查清理和若干 bug 修复，并补充了单元测试。原项目的使用方法、安装方式和 GPL-3.0 许可证均保持不变，中文使用指南见 [USAGE_zh-CN.md](USAGE_zh-CN.md)，英文说明见 [README.md](README.md)、[INSTALL.md](INSTALL.md) 和 [USAGE.md](USAGE.md)。

**新手推荐：** 新增中文简易网页界面（基于 Gradio，向导式三步：提取 → 训练 → 转换），`pip install gradio` 后运行 `python app.py` 即可，详见 [SIMPLE_GUI_zh-CN.md](SIMPLE_GUI_zh-CN.md)。Windows + NVIDIA 显卡用户可直接在 Releases 下载安装包 `FaceswapSimple-Setup.exe`，安装即用，见下方「Windows 小白操作步骤」。

> 请合法、合规地使用本项目：仅在获得当事人同意的素材上使用换脸技术，遵守原项目的伦理声明与所在地法律。

## Windows 小白操作步骤（不用敲命令）

> 适用于 Releases 里的安装包 `FaceswapSimple-Setup.exe`。哪一步卡住了，请截图「运行日志」提 issue。

### 第 0 步：确认电脑能用（2 分钟）

1. 同时按 **Ctrl + Shift + Esc** 打开「任务管理器」，点左侧「性能」→「GPU」，右上角应写着 **NVIDIA GeForce RTX ……**（20、30、40、50 系列都可以）。是 GTX、Intel 或 AMD 显卡则用不了这个版本。
2. 按 **Win 键**，输入 `cmd` 回车，在黑窗口里输入 `nvidia-smi` 回车。**Driver Version** 是 580 或更大就行；小于 580 先到 NVIDIA 官网下载最新驱动安装，然后重启电脑。

### 第 1 步：下载（3 个文件）

1. 打开本仓库右侧的 **Releases**，进入最新版本，下载 **`FaceswapSimple-Setup.exe`、`FaceswapSimple-Setup-1.bin`、`FaceswapSimple-Setup-2.bin`**。
2. 等三个文件都下完（两个 .bin 分别约 1.8 GB 和 1.2 GB），确认它们在**同一个文件夹**里，文件名不要改。

### 第 2 步：安装（约 10 分钟）

1. 双击 **FaceswapSimple-Setup.exe**。
2. 弹出蓝色的「Windows 已保护你的电脑」时：点「**更多信息**」→「**仍要运行**」。
3. 说明页点「下一步」；许可协议选「我同意」→「下一步」。
4. 安装位置默认 `C:\FaceswapSimple`；C 盘空间不足 15 GB 就改成 `D:\FaceswapSimple`。不要装进 `Program Files`，路径里不要有中文和空格。
5. 勾上「**创建桌面快捷方式**」→「下一步」→「安装」，进度条跑完后点「完成」。

### 第 3 步：打开程序

1. 双击桌面上的「**Faceswap 简易版**」。
2. 会先出现一个**黑色窗口**，这是程序本体，**全程不要关它**。
3. 等 10 秒到 2 分钟，浏览器会自动打开中文页面；没打开就在浏览器地址栏输入 `127.0.0.1:7860` 回车。
4. 页面顶部勾选「**我已阅读并同意使用须知**」，「预设模式」选「**新手模式**」。

### 第 4 步：设置工作文件夹（只做一次）

1. 在页面顶部「**📁 工作文件夹**」里填一个英文路径，例如 `D:\fs`（没有 D 盘就填 `C:\fs`，放桌面也行，如 `C:\Users\Administrator\Desktop\fmx`）。
2. 点「**✔ 应用并自动填好所有路径**」。程序会自动建好下面这些文件夹，并把 ①②③ 和视频工具里所有路径都填好，**下次打开自动沿用**：

```
D:\fs\A        ← 放 A 的素材：要被换掉脸的人（1 个视频，或若干 jpg/png 照片）
D:\fs\B        ← 放 B 的素材：要换上去的那张脸
D:\fs\facesA   提取出的 A 人脸（自动生成）
D:\fs\facesB   提取出的 B 人脸（自动生成）
D:\fs\model    训练出的换脸模型（自动生成）
D:\fs\output   换脸成品（自动生成）
D:\fs\frames   视频工具拆出的图片
```

各步骤自动填入的路径（以 `D:\fs` 为例）：

| 位置 | 自动填入 |
|---|---|
| ① 提取（点「填入 A」） | 输入 `D:\fs\A` → 输出 `D:\fs\facesA` |
| ① 提取（点「填入 B」） | 输入 `D:\fs\B` → 输出 `D:\fs\facesB` |
| ② 训练 | A `D:\fs\facesA`，B `D:\fs\facesB`，模型 `D:\fs\model` |
| ③ 转换 | 输入 `D:\fs\A`，输出 `D:\fs\output`，模型 `D:\fs\model` |
| 视频工具：视频 → 图片 | `D:\fs\A` → `D:\fs\frames` |
| 视频工具：图片 → 视频 | `D:\fs\output` → `D:\fs\result.mp4` |

> 以前用旧版提取过人脸、文件夹名不一样（比如 `outputA`）：把它改名成 `facesA`（B 同理）就能接着用，不用重新提取。
> 想换工作文件夹：在顶部改成新路径，再点一次「应用」。

3. 打开 `D:\fs\A`，把 A 的视频（或照片）复制进去；打开 `D:\fs\B`，把 B 的视频（或照片）复制进去。
   - 每个文件夹**只放一个视频**（会自动识别），或者只放照片，不要再套子文件夹。
   - 每个视频里最好只有这一个人，脸清楚，几分钟以上最好。webp、heic、jfif 照片要先转成 jpg。

> 不想用工作文件夹也可以在每一栏手动填完整路径。小技巧：右键文件或文件夹 →「复制文件地址」/「复制为路径」，可以直接粘贴，带引号也没关系。

### 第 5 步：提取人脸（A、B 各一次）

1. 点「**① 提取人脸**」标签，点「**👤 填入 A 的路径**」（输入变成 `D:\fs\A`，输出变成 `D:\fs\facesA`），点「**▶ 开始提取**」。
2. 等状态从 ⏳ 运行中 变成 ✅ **已完成**。
3. 点「**👤 填入 B 的路径**」，再点「▶ 开始提取」，等到 ✅ 已完成。
4. **挑图（很重要）**：打开 `facesA`，右键 → 查看 → 大图标，删掉不是这个人的、模糊的、被挡住的脸；`facesB` 同样处理。每边至少 25 张，最好几百张以上。
5. `A`、`B` 文件夹里多出来的 `*_alignments.fsa` 文件**不要删**，第 7 步要用。

### 第 6 步：训练模型（最耗时）

1. 点「**② 训练模型**」标签，三个路径已经自动填好（`facesA`、`facesB`、`model`）。
2. 点「**▶ 开始训练**」。右边「训练预览」每次保存时刷新，从模糊色块慢慢变清楚，新手模式一般要几个小时。
3. 预览里换出来的脸够清楚了，点「**⏹ 停止**」。想接着练，下次直接再点开始，会从上次保存的地方继续。
4. 黑色窗口出现 out of memory（显存不足）：展开「高级设置」，把「批大小」从 8 改成 4，重新开始。

> 「模型文件夹」不是内置的：内置的只是找人脸用的通用模型，换脸模型要用你的 A、B 两张脸现场训练，保存在 `model` 文件夹里。

### 第 7 步：生成换脸视频

1. 点「**③ 转换换脸**」标签，路径已经自动填好（输入 `A`、输出 `output`、模型 `model`）。
2. 点「**▶ 开始转换**」，等到 ✅ 已完成，打开 `D:\fs\output` 就是成品。

### 视频工具（可选，新手可跳过）

- 选「视频 → 图片」：自动填 `A` → `frames`，把 A 的视频拆成图片。
- 选「图片 → 视频」：自动填 `output` → `result.mp4`，把转换出的图片合成视频（转换视频时成品已经是视频，一般不需要）。

### 用完怎么关

先关浏览器页面，再关黑色窗口。只关浏览器的话程序还在后台运行。

### 常见问题

| 现象 | 原因与解决 |
|---|---|
| 提示「没有找到可处理的图片或视频帧」，日志里 `Images found: 0` | 输入框填的文件夹里没有 jpg/png 图片。v1.1.1 起文件夹里只有**一个视频**时会自动使用它；放了多个视频时请直接填视频文件本身。照片要直接放在该文件夹里，webp/heic/jfif 先转成 jpg。新版会在开始前直接提示具体原因。 |
| 图片文件夹只处理了一小部分照片 | 旧版「新手模式」的「每 5 帧提取一次」也作用在照片上；新版只对视频生效。旧版请在「高级设置」里把它改成 1。 |
| 提取一直 0%，日志里有 `Downloading model` / `timed out` | 旧版需要从 GitHub 下载模型，请升级到 v1.1.0 及以上（已内置模型）。 |
| 「模型文件夹」不是内置了吗？ | 内置的是「找人脸、对齐人脸」用的通用模型。换脸模型要用你自己的 A、B 两张脸现场训练，「模型文件夹」就是用来保存它的地方：第一次训练填一个新的空文件夹（如 `D:\fs\model`），之后转换和继续训练都填同一个。 |
| 页面提示「路径不存在」 | 检查盘符、文件名和扩展名是否写对。 |
| 提示「没检测到人脸」 | 换一个脸更大、更清楚、正脸更多的素材。 |
| 提示「已有任务正在运行」 | 一次只能做一件事，等它完成或先点停止。 |
| 显卡 / NVML / CUDA 报错 | 回到第 0 步更新显卡驱动并重启。GTX 10 系列及更老显卡不支持。 |
| 想换端口 | 在 cmd 里运行 `"D:\FaceswapSimple\FaceswapSimple.exe" --port 8000`。 |

更多说明见 [WINDOWS_TUTORIAL_zh-CN.md](WINDOWS_TUTORIAL_zh-CN.md) 和 [SIMPLE_GUI_zh-CN.md](SIMPLE_GUI_zh-CN.md)。

## 改动总览

| 指标 | 重构前（master） | 重构后（main） |
|---|---|---|
| pytest（仅 CPU） | 618 个测试，617 通过 | 667 个测试，666 通过（新增 49 个） |
| 命令行帮助冒烟测试（14 个入口） | 全部正常 | 全部正常，输出逐字节一致 |
| 模块导入（274 个） | 273 正常 | 273 正常 |
| ruff E/W/F 问题 | 33 | 0 |
| ruff 复杂度告警 C901 | 10 | 0 |
| 无效的 `noqa` 注释 | 40 | 0 |
| pylint 评分 / 错误数 | 9.98 / 8 个错误 | 9.99 / 0 个错误 |
| 缺少返回值类型标注的函数 | 657 | 616 |
| 缺少类型标注的参数 | 818 | 755 |

唯一失败的测试 `tests/tools/alignments/media_test.py::TestFrames::test_process_folder` 在重构前后都会失败，原因是测试环境（ARM 架构）缺少 ffmpeg 二进制文件，与代码无关；指定系统 ffmpeg 后该文件 27/27 全部通过。

## 修复的 bug

这是唯一有意改变行为的部分，且只涉及原本就会出错的代码路径：

1. **GUI 训练图表崩溃**（`lib/gui/display_graph.py`）：`matplotlib.cm.get_cmap` 已在 matplotlib 3.9 中移除，而项目要求 ≥3.10，导致生成图表颜色时报 `AttributeError`。现改用 `matplotlib.colormaps[name]`。
2. **TensorBoard 日志读取**（`lib/gui/analysis/event_reader.py`）：缓存在创建之前就可能被调用 `reset()`，现调整为先创建缓存。
3. **序列化器查找**（`lib/serializer.py`）：未知名称原来返回 `None`，现返回 JSON 序列化器；缺少 PyYAML 时原来返回“类”而不是“实例”，现已修正。
4. **`tools.py`**：`bad_args()` 依赖一个只在直接运行脚本时才存在的全局变量，现将命令行构建移入 `_main()`，帮助输出不变。

## 代码重构

- **拆分过长函数**（拆分前先针对原代码编写测试并确认通过，保证行为一致）：
  - `lib/image.py` 的 `read_image()` 拆为 `_decode_image()` 和 `_handle_read_error()`，异常类型和信息保持不变。
  - `plugins/train/model/_base/state.py` 的 `State._update_legacy_config()`（98 行）拆为 7 个小方法，按顺序表分发。
  - `lib/video.py` 的 `count_frames()` 提取出 FFmpeg 输出解析函数，并用 `with` 管理子进程。
- **去重**：`lib/cli/actions.py` 中三处重复的 argparse 参数列表合并为一个常量 `_BASE_KWARGS`。
- **类型标注**：`lib/serializer.py`、`lib/image.py`、`lib/cli/actions.py` 补全类型标注，mypy 检查通过。
- **删除死代码**：`read_image` 中不可达的分支，以及 `tools/preview/preview.py` 无限循环之后不可达的语句。

## 静态检查清理

- 修正 39 处格式错误的 `# noqa[...]` 注释（原来被 flake8 当成“全部忽略”，掩盖了 3 个真实问题）。
- 12 处 `x == bool/int/...` 类型比较改为 `is`，以及其他小问题。
- 只应用 ruff 的**安全**自动修复，例如 `class X():` → `class X:`、`range(0, n)` → `range(n)`、去掉多余的 `pass` 等。
- `pyproject.toml` 新增 `[tool.ruff]` 配置，与原有 flake8 规则保持一致（行宽 99、复杂度上限 10）。

## 新增测试

| 测试文件 | 数量 | 内容 |
|---|---|---|
| `tests/lib/serializer_test.py` | 20 | 序列化器读写与查找（其中 2 个在原代码上失败，用于记录修复的 bug） |
| `tests/lib/image_test.py` | 14 | 图像读取与解码行为 |
| `tests/lib/video_test.py` | 4 | FFmpeg 输出解析与帧计数 |
| `tests/plugins/train/model/state_test.py` | 11 | 旧版训练配置迁移 |

## 有意未改动的部分

- **打包方式**：`setup.py` 是交互式安装程序而非 setuptools 脚本，改成可 pip 安装会影响部署方式，因此未改。
- **很长的 argparse 选项定义**：属于纯声明式代码，拆分意义不大。
- **import 排序**：改动量大、收益小。
- **4 通道图像的 alpha 通道**：仍按原行为保留，仅在代码中加了注释说明。

## 测试说明与局限

- 测试在 CPU（PyTorch CPU 版 + Keras torch 后端）上进行，无 GPU。
- 未进行真实的提取、训练、转换全流程运行（需要 GPU 和大型模型/数据），这些路径依靠单元测试、模块导入和命令行冒烟测试覆盖。
- 未运行端到端脚本 `tests/simple_tests.py`。

## 运行测试

```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements/_requirements_base.txt pytest
export KERAS_BACKEND=torch
pytest tests
```

## 许可证

与上游项目相同，采用 [GPL-3.0](LICENSE) 许可证。
