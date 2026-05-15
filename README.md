# KeyOCR

Smart video keyframe extraction and OCR text recognition tool. Built with PySide6 GUI + OpenCV, automatically extracts keyframes from videos and batch-recognizes text.

[简体中文](README_zh-CN.md) | [繁體中文](README_zh-TW.md)

## Features

- **Smart Frame Extraction** — Scene change detection with 14x compression ratio
- **Auto OCR Region Detection** — Sobel edge detection + voting mechanism to locate subtitle regions
- **Batch OCR** — Windows GPU (PaddleOCR 3.x) / macOS CPU (RapidOCR), auto-switching
- **OCR Text Deduplication** — Merges duplicate text across adjacent frames, reducing 45% redundancy
- **AI Text Correction** — Calls LLM API to automatically fix OCR errors
- **Batch Processing** — Queue multiple videos, auto-skip failures
- **One-Click Extract** — Frame extraction → region detection → OCR → AI correction, fully automated

## Download

Go to the [Releases](../../releases/latest) page:

| Platform | File | Description |
|----------|------|-------------|
| Windows | `KeyOCR_Setup.exe` | Installer (recommended) |
| Windows | `KeyOCR.exe` | Portable version |
| macOS | `KeyOCR-macOS.zip` | Unzip and double-click to run |

### Windows

Download `KeyOCR_Setup.exe`, install and run.

GPU acceleration requires NVIDIA GPU + CUDA 11.8. Falls back to CPU OCR automatically if unavailable.

### macOS

Download `KeyOCR-macOS.zip`, unzip and drag `KeyOCR.app` to Applications.

If macOS says "cannot verify developer", right-click → Open.

## Build from Source

```bash
git clone https://github.com/Ha1baraA11/KeyOCR.git
cd KeyOCR
```

**macOS:**
```bash
pip install PySide6 opencv-contrib-python==4.10.0.84 numpy rapidocr-onnxruntime
python frame_extractor_gui.py
```

**Windows (GPU):**
```bash
python -m pip install opencv-contrib-python==4.10.0.84
python -m pip install paddlepaddle-gpu==3.3.0 -i https://www.paddlepaddle.org.cn/packages/stable/cu118/
python -m pip install paddleocr "paddlex[ocr]" pypdfium2 PySide6 numpy
python frame_extractor_gui.py
```

## Project Structure

| File | Description |
|------|-------------|
| `frame_extractor_gui.py` | Main app (GUI + algorithms + batch OCR + region detection) |
| `frame_extractor.spec` | PyInstaller build config |
| `frame_extractor.iss` | Inno Setup installer script |
| `runtime_hook_cv2.py` | PyInstaller runtime hook |
| `build.bat` | Windows local build script |
| `detect_region.py` | Region detection test script |
| `merge_ocr.py` | OCR result merge/dedup script |
| `run_test.py` | Test script |
| `智能筛选算法迭代.md` | Algorithm iteration notes |

## OCR Engines

| Engine | Platform | Dependencies |
|--------|----------|-------------|
| PaddleOCR 3.x | Windows (CUDA) | `paddlepaddle-gpu` + `paddlex[ocr]` |
| RapidOCR | macOS / Windows CPU fallback | `rapidocr-onnxruntime` |

Auto-detects CUDA availability, falls back to CPU OCR when unavailable.

## Configuration

Settings are saved in `config.json` next to the executable:

- **API Settings** — API URL, Key, model name
- **OCR Engine** — Auto / Force CPU / Force GPU
- **OCR Region** — Auto detect / Manual selection
- **AI Prompt** — Custom correction template, `{ocr_text}` as placeholder
- **Auto Cleanup** — Delete intermediate files after AI correction

## License

MIT
