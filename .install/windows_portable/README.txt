Faceswap 简易版 · Windows NVIDIA 便携包
=====================================

使用方法
1. 把所有分卷（.7z.001、.7z.002 ……）放在同一个文件夹，用 7-Zip 打开 .7z.001 解压。
   解压路径建议不要太深，例如 D:\FaceswapSimple。
2. 双击 FaceswapSimple.exe。会出现一个黑色窗口（日志），浏览器随后自动打开
   http://127.0.0.1:7860 。使用期间不要关闭黑色窗口，关闭它就退出程序。
3. 在页面里勾选使用声明，按「提取人脸 → 训练模型 → 转换换脸」的顺序操作。
   详细说明见 faceswap\SIMPLE_GUI_zh-CN.md。

硬件要求
- NVIDIA RTX 20 系列或更新的显卡（CUDA 13，算力 7.5 及以上）。
- 显卡驱动 580 或更新版本（在 NVIDIA 官网或 GeForce Experience 更新）。
- 64 位 Windows 10/11，建议 16 GB 以上内存，至少 10 GB 可用磁盘空间。
- 无需单独安装 Python、CUDA 或 cuDNN，已全部内置。

注意
- 第一次提取或训练时会联网下载模型权重，存放在 faceswap\.fs_cache。
- 启动参数：FaceswapSimple.exe --port 8000（改端口）、--no-browser（不自动打开浏览器）。
- 仅可用于已获得当事人同意的素材，并遵守当地法律。本软件以 GPL-3.0 许可发布。
