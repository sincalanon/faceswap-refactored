# 重构与修复说明

本文记录 faceswap-refactored 相对上游 [deepfakes/faceswap](https://github.com/deepfakes/faceswap)（`master` @ `f530cb7`）在核心代码上的改动，面向开发者。普通用户请看 [README_zh-CN.md](../README_zh-CN.md)。

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

