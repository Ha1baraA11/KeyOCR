# KeyOCR

视频智能分帧 + OCR 文字提取工具。基于 PySide6 GUI + OpenCV，从视频中自动提取关键帧并批量识别文字。

[English](README.md) | [繁體中文](README_zh-TW.md)

## 功能

- **智能分帧** — 场景转换点检测，自动提取关键帧，14x 压缩率
- **自动 OCR 区域检测** — Sobel 边缘 + 投票机制，自动定位字幕区域
- **批量 OCR** — Windows GPU (PaddleOCR 3.x) / macOS CPU (RapidOCR)，自动切换
- **OCR 文本合并去重** — 相邻帧重复文本自动合并，减少 45% 冗余
- **AI 文字纠错** — 调用大模型 API 自动修正 OCR 错误
- **批处理** — 多个视频排队处理，失败自动跳过
- **一键提取** — 分帧 → 区域检测 → OCR → AI 纠错，全流程自动

## 下载

前往 [Releases](../../releases/latest) 页面下载：

| 平台 | 文件 | 说明 |
|------|------|------|
| Windows | `KeyOCR_Setup.exe` | 安装程序（推荐） |
| Windows | `KeyOCR.exe` | 便携版 |
| macOS | `KeyOCR-macOS.zip` | 解压后双击运行 |

### Windows 用户

下载 `KeyOCR_Setup.exe`，安装后双击运行。

GPU 加速需 NVIDIA 显卡 + CUDA 11.8。无显卡时自动使用 CPU OCR。

### macOS 用户

下载 `KeyOCR-macOS.zip`，解压后将 `KeyOCR.app` 拖入 Applications 文件夹。

首次运行如提示"无法验证开发者"，右键 → 打开 即可。

## 从源码运行

```bash
git clone https://github.com/Ha1baraA11/KeyOCR.git
cd KeyOCR
```

**macOS：**
```bash
pip install PySide6 opencv-contrib-python==4.10.0.84 numpy rapidocr-onnxruntime
python frame_extractor_gui.py
```

**Windows（GPU）：**
```bash
python -m pip install opencv-contrib-python==4.10.0.84
python -m pip install paddlepaddle-gpu==3.3.0 -i https://www.paddlepaddle.org.cn/packages/stable/cu118/
python -m pip install paddleocr "paddlex[ocr]" pypdfium2 PySide6 numpy
python frame_extractor_gui.py
```

## 项目结构

| 文件 | 说明 |
|------|------|
| `frame_extractor_gui.py` | 主程序（GUI + 所有算法 + 批量 OCR + 区域检测） |
| `frame_extractor.spec` | PyInstaller 打包配置 |
| `frame_extractor.iss` | Inno Setup 安装程序脚本 |
| `runtime_hook_cv2.py` | PyInstaller runtime hook |
| `build.bat` | Windows 本地打包脚本 |
| `detect_region.py` | 区域检测测试脚本 |
| `merge_ocr.py` | OCR 结果合并去重脚本 |
| `run_test.py` | 测试脚本 |
| `智能筛选算法迭代.md` | 算法迭代过程记录 |

## OCR 引擎

| 引擎 | 平台 | 依赖 |
|------|------|------|
| PaddleOCR 3.x | Windows (CUDA) | `paddlepaddle-gpu` + `paddlex[ocr]` |
| RapidOCR | macOS / Windows CPU 回退 | `rapidocr-onnxruntime` |

程序自动检测 CUDA 可用性，不可用时自动回退到 CPU OCR。

## 配置

设置保存在程序同目录的 `config.json`，支持配置：

- **API 设置** — API URL、Key、模型名称
- **OCR 引擎** — 自动 / 强制 CPU / 强制 GPU
- **OCR 区域** — 自动检测 / 手动框选
- **AI 提示词** — 自定义纠错模板，`{ocr_text}` 为占位符
- **自动清理** — AI 纠错后自动删除中间文件

## License

MIT
