# faceswap 重构版使用指南

> 请仅对获得本人同意的素材使用，并遵守当地法律与原项目的伦理声明。

## 1. 安装

推荐使用 Miniconda（会自动处理 CUDA/cuDNN）：

```bash
git clone https://github.com/sincalanon/-faceswap-refactored.git faceswap
cd faceswap
conda create --name faceswap python=3.13
conda activate faceswap
python setup.py        # 按提示选择 NVIDIA / AMD / CPU 等
conda install tk       # 图形界面需要
```

以后更新依赖：`python update_deps.py`

> 注意：官方 Windows 安装包（faceswap_setup_x64.exe）安装的是上游原版，要使用本重构版请按上面方式从本仓库克隆。

## 2. 图形界面（最简单）

```bash
python faceswap.py gui
```

界面里有 Extract / Train / Convert 三个标签页，鼠标悬停在选项上会显示说明。

**更简单的中文网页版（推荐新手）：** `pip install gradio` 后运行 `python app.py`，在浏览器中按「提取 → 训练 → 转换」三步操作，只显示常用参数。详见 [SIMPLE_GUI_zh-CN.md](SIMPLE_GUI_zh-CN.md)。

## 3. 命令行三步

### 第一步：提取人脸

A、B 两个人各做一次，输入可以是图片文件夹或视频：

```bash
python faceswap.py extract -i ~/faceswap/src/personA.mp4 -o ~/faceswap/faces/A
python faceswap.py extract -i ~/faceswap/src/personB.mp4 -o ~/faceswap/faces/B
```

提取后建议手动删掉识别错的、模糊的脸。

### 第二步：训练模型

`-p` 显示实时预览：

```bash
python faceswap.py train -A ~/faceswap/faces/A -B ~/faceswap/faces/B -m ~/faceswap/model_AB -p
```

通常要训练几小时到几天，预览效果满意后按 Enter 保存退出。

### 第三步：转换

```bash
python faceswap.py convert -i ~/faceswap/src/personA.mp4 -o ~/faceswap/converted/ -m ~/faceswap/model_AB
```

## 4. 其他

- 查看每个命令的全部选项：`python faceswap.py extract -h`（train、convert 同理）
- 辅助工具（对齐、排序、遮罩、预览等）：`python tools.py -h`
- 运行测试：`pip install pytest && pytest tests`

## 5. 注意

- 训练强烈建议使用 NVIDIA 显卡；CPU 也能运行，但会非常慢。
- 更多英文说明见 [INSTALL.md](INSTALL.md) 和 [USAGE.md](USAGE.md)。
