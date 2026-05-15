<p align="center">
  <img src="KeyOCR_logo.png" alt="KeyOCR Logo" width="200">
</p>

<h1 align="center">KeyOCR</h1>

<p align="center">
  <strong>视频智能分帧 + OCR 文字提取工具</strong><br>
  从视频中自动提取关键帧，批量识别文字，纠错输出最终结果
</p>

<p align="center">
  <a href="README.md">English</a> · <a href="README_zh-TW.md">繁體中文</a>
</p>

---

## 功能特性

| 功能 | 说明 |
|------|------|
| **智能分帧** | 基于场景转换点检测，自动提取关键帧，14x 压缩率（4020 帧 → 96 帧） |
| **自动 OCR 区域检测** | Sobel 边缘检测 + 投票机制，自动定位字幕区域 |
| **手动 OCR 区域选择** | 支持鼠标框选自定义 OCR 识别区域 |
| **批量 OCR** | Windows GPU（PaddleOCR 3.x）/ macOS CPU（RapidOCR），自动切换 |
| **OCR 文本合并去重** | 前缀重叠、扩展关系、后缀拼接，减少 45% 冗余 |
| **AI 文字纠错** | 调用大模型 API 自动修正 OCR 错误，支持自定义提示词 |
| **批处理模式** | 多个视频排队处理，失败自动跳过 |
| **一键提取** | 分帧 → 区域检测 → OCR → AI 纠错，全流程自动化 |
| **中文路径兼容** | Windows 中文目录/文件名全程兼容（符号链接 + imencode 回退） |

## 下载安装

前往 [Releases](../../releases/latest) 页面下载：

| 平台 | 文件 | 说明 |
|------|------|------|
| Windows | `KeyOCR_Setup.exe` | 安装程序（推荐），默认安装到 `D:\KeyOCR` |
| Windows | `KeyOCR.exe` | 便携版，解压即用 |
| macOS | `KeyOCR-macOS.zip` | 解压后双击运行 |

### Windows

1. 下载 `KeyOCR_Setup.exe`
2. 运行安装程序，可自定义安装目录（建议英文路径）
3. 双击桌面快捷方式启动

> **GPU 加速**：需 NVIDIA 显卡 + CUDA 11.8 + cuDNN。无显卡时自动使用 CPU OCR，无需额外配置。

### macOS

1. 下载 `KeyOCR-macOS.zip`
2. 解压后将 `KeyOCR.app` 拖入 Applications
3. 首次运行如提示"无法验证开发者"，右键 → 打开

> macOS 仅支持 CPU OCR（RapidOCR），无需安装额外依赖。

## 使用方法

### 基本流程

1. **选择视频** — 点击"选择视频"按钮，支持多选（多选自动开启批处理）
2. **一键提取** — 点击"一键提取"，自动完成：
   - 智能分帧：检测场景转换点，提取关键帧
   - 区域检测：自动定位字幕区域（也可手动框选）
   - 批量 OCR：逐帧识别文字
   - 文本合并：去重合并相邻帧重复内容
   - AI 纠错：调用大模型修正 OCR 错误
3. **查看结果** — 点击"打开文件夹"查看输出

### 设置说明

点击右上角"设置"按钮可配置：

- **API 设置** — 填写 API URL、Key、模型名称（AI 纠错必须）
- **OCR 引擎** — 自动 / 强制 CPU / 强制 GPU
- **OCR 区域** — 自动检测 / 手动框选
- **AI 提示词** — 自定义纠错模板，使用 `{ocr_text}` 作为 OCR 文本占位符
- **自动清理** — 开启后 AI 纠错完成自动删除中间文件，只保留最终结果
- **清除缓存** — 删除所有中间帧图片，保留最终版文件

### 输出目录

- 中间帧：`{安装目录}/cache/{视频名}_frames/`
- 最终结果：`{安装目录}/最终版/{视频名}-最终版.txt`

## 从源码运行

```bash
git clone https://github.com/Ha1baraA11/KeyOCR.git
cd KeyOCR
```

### macOS（CPU）

```bash
pip install PySide6 opencv-contrib-python==4.10.0.84 numpy rapidocr-onnxruntime
python frame_extractor_gui.py
```

### Windows（GPU）— 完整安装指南

#### 前置条件

| 组件 | 版本 | 说明 |
|------|------|------|
| Python | 3.10 或 3.12 | paddlepaddle-gpu 不支持 3.13+ |
| NVIDIA 显卡 | 任意支持 CUDA 的显卡 | 推荐 RTX 20/30/40 系列 |
| CUDA Toolkit | 11.8 | 必须与 paddlepaddle-gpu 版本匹配 |
| cuDNN | 8.6+（对应 CUDA 11.8） | PaddlePaddle 运行必需 |

#### 第一步：安装 CUDA Toolkit 11.8

1. 打开 [NVIDIA CUDA Toolkit 归档页](https://developer.nvidia.com/cuda-toolkit-archive)
2. 选择 **CUDA Toolkit 11.8.0**
3. 选择系统配置：**Windows → x86_64 → 10/11 → exe (local)**
4. 下载约 3 GB 的安装包
5. 运行安装程序，选择 **自定义（高级）**
6. 确保勾选 **CUDA > Development** 和 **CUDA > Runtime**
7. 完成安装

验证安装：

```bash
nvcc --version
# 应输出：Cuda compilation tools, release 11.8
```

> 如果提示 `nvcc` 找不到，需要将 `C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v11.8\bin` 添加到系统 PATH 环境变量。

#### 第二步：安装 cuDNN

1. 打开 [NVIDIA cuDNN 下载页](https://developer.nvidia.com/rdp/cudnn-archive)（需要注册免费 NVIDIA 账号）
2. 选择 **cuDNN v8.6.0（或更高版本）for CUDA 11.x**
3. 下载 **Windows** 版本的 zip 文件
4. 解压后将文件复制到 CUDA 安装目录：
   - `bin\cudnn*.dll` → `C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v11.8\bin`
   - `include\cudnn*.h` → `C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v11.8\include`
   - `lib\x64\cudnn*.lib` → `C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v11.8\lib\x64`

#### 第三步：安装 Python 依赖

打开 PowerShell 或 CMD，按顺序执行：

```bash
# 1. 安装 Python（3.10 或 3.12，不要用 3.13+）
#    下载地址：https://www.python.org/downloads/
#    安装时勾选 "Add Python to PATH"

# 2. 卸载冲突的 OpenCV 包
python -m pip uninstall opencv-python opencv-contrib-python opencv-python-headless -y

# 3. 安装 OpenCV（必须用 contrib 版本，锁定 4.10.0.84）
python -m pip install opencv-contrib-python==4.10.0.84

# 4. 安装 PaddlePaddle GPU 版（必须用百度官方镜像，不能用 PyPI）
python -m pip install paddlepaddle-gpu==3.3.0 -i https://www.paddlepaddle.org.cn/packages/stable/cu118/

# 5. 安装 PaddleOCR 和 PaddleX
python -m pip install paddleocr "paddlex[ocr]" pypdfium2

# 6. 安装 PaddleOCR 运行时依赖
python -m pip install pandas scipy scikit-image shapely pyclipper rapidfuzz lmdb pyyaml tqdm protobuf Pillow requests

# 7. 安装 GUI 框架
python -m pip install PySide6 numpy
```

> **重要提示**：`paddlepaddle-gpu` 不在 PyPI 上，必须使用 PaddlePaddle 官方镜像（`-i https://www.paddlepaddle.org.cn/...`）。如果用 `pip install paddlepaddle` 从 PyPI 安装，装的是 CPU 版本，不支持 GPU 加速。

#### 第四步：运行程序

```bash
python frame_extractor_gui.py
```

#### 第五步：验证 GPU 是否正常工作

在程序中打开 设置 → OCR 引擎，应显示"GPU (PaddleOCR)"可用。

或手动验证：

```bash
python -c "import paddle; print('CUDA:', paddle.device.is_compiled_with_cuda())"
# 应输出：CUDA: True
```

### Windows（CPU，无显卡）

如果没有 NVIDIA 显卡，使用简化的 CPU 方案：

```bash
python -m pip install opencv-contrib-python==4.10.0.84 PySide6 numpy rapidocr-onnxruntime
python frame_extractor_gui.py
```

### 环境验证

```bash
python -c "import cv2; print('cv2:', cv2.__version__)"
python -c "import paddle; print('paddle:', paddle.__version__, 'CUDA:', paddle.device.is_compiled_with_cuda())"
python -c "import paddleocr; import paddlex; print('paddleocr+paddlex OK')"
python -c "from rapidocr_onnxruntime import RapidOCR; print('rapidocr OK')"
```

## Windows 打包

### 自动打包（CI）

Push 到 main 分支自动触发 GitHub Actions：构建 → 自检 → 创建 Release。

### 本地打包

```bash
# 双击 build.bat 或手动执行：
python -m pip install pyinstaller
pyinstaller frame_extractor.spec
```

打包后自动运行自检（`KEYOCR_SELF_CHECK=1`），验证 EXE 内模块完整性 + CUDA 可用性。

### 生成安装程序

打包完成后，使用 Inno Setup 打开 `frame_extractor.iss` 编译生成安装程序。

## OCR 引擎

| 引擎 | 平台 | 依赖 | 说明 |
|------|------|------|------|
| PaddleOCR 3.x | Windows (CUDA) | `paddlepaddle-gpu` + `paddlex[ocr]` | GPU 加速，速度快 |
| RapidOCR | macOS / Windows CPU 回退 | `rapidocr-onnxruntime` | 纯 CPU，无需 GPU |

程序启动时自动检测 CUDA 可用性：
- Windows + CUDA 可用 → PaddleOCR（GPU）
- Windows + CUDA 不可用 → RapidOCR（CPU），日志提示原因
- macOS → 始终使用 RapidOCR（CPU）

## 算法说明

### 智能分帧

基于视频场景转换点检测：

1. 以 9fps 粗扫截帧
2. 计算相邻帧差异，检测峰值（差异 > 中位数 × 1.5）
3. 每个峰值只取 1 帧，避免冗余

### OCR 区域检测

Sobel 水平边缘 + 投票机制：

1. 从提取的帧中采样 16 帧
2. 每帧独立检测字幕区域（Sobel 边缘 → 行聚类 → 取最强两个聚类）
3. 投票取中位数，确保稳定性

### OCR 文本合并

四种合并策略：
- **前缀重叠**：当前帧是前一帧的前缀 → 跳过
- **扩展关系**：前一帧是当前帧的前缀 → 替换为更长版本
- **公共前缀**：重叠超过 50% → 保留最长版本
- **后缀重叠**：前一帧后缀 = 当前帧前缀 → 拼接成完整句子

## 项目结构

```
KeyOCR/
├── frame_extractor_gui.py    # 主程序（GUI + 算法 + OCR + AI 纠错）
├── frame_extractor.spec      # PyInstaller 打包配置
├── frame_extractor.iss       # Inno Setup 安装程序脚本
├── runtime_hook_cv2.py       # PyInstaller runtime hook
├── build.bat                 # Windows 本地打包脚本
├── detect_region.py          # 区域检测独立测试脚本
├── merge_ocr.py              # OCR 结果本地合并去重脚本
├── run_test.py               # 测试脚本
├── test_region_detect.py     # 区域检测单元测试
├── icon.ico                  # 应用图标
├── KeyOCR_logo.png           # 项目 Logo
└── requirements.txt          # Python 依赖清单
```

## 常见问题

### GPU OCR 不工作

1. 确认有 NVIDIA 显卡：`nvidia-smi`
2. 确认 CUDA 11.8 已安装：`nvcc --version`
3. 确认 paddle 是 GPU 版：`python -c "import paddle; print(paddle.device.is_compiled_with_cuda())"`
4. 如果输出 False，重新安装：`python -m pip install paddlepaddle-gpu==3.3.0 -i https://www.paddlepaddle.org.cn/packages/stable/cu118/`

### PaddleX 模型缓存损坏

清除缓存目录后重新运行：
- Windows：`rmdir /s /q C:\Users\{用户名}\.paddlex`
- macOS/Linux：`rm -rf ~/.paddlex`

### 中文路径报错

程序已内置中文路径兼容，如仍遇问题：
- 将视频移到英文路径下
- 或使用安装版（默认安装到 `D:\KeyOCR`）

### AI 纠错不生效

1. 确认已在设置中填写 API Key
2. 确认 API URL 可访问
3. 检查模型名称是否正确

## 技术栈

- **GUI**：PySide6（Qt for Python）
- **视频处理**：OpenCV
- **OCR**：PaddleOCR 3.x（GPU）/ RapidOCR（CPU）
- **AI 纠错**：OpenAI 兼容 API（支持任意兼容接口）
- **打包**：PyInstaller + Inno Setup

## License

MIT
