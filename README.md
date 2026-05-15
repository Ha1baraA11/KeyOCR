<p align="center">
  <img src="KeyOCR_logo.png" alt="KeyOCR Logo" width="200">
</p>

<h1 align="center">KeyOCR</h1>

<p align="center">
  <strong>Smart video keyframe extraction + OCR text recognition</strong><br>
  Automatically extract keyframes from videos, batch-recognize text, and output corrected results
</p>

<p align="center">
  <a href="README_zh-CN.md">简体中文</a> · <a href="README_zh-TW.md">繁體中文</a>
</p>

---

## Features

| Feature | Description |
|---------|-------------|
| **Smart Frame Extraction** | Scene change detection, auto-extract keyframes, 14x compression (4020 frames → 96) |
| **Auto OCR Region Detection** | Sobel edge detection + voting mechanism to locate subtitle regions |
| **Manual OCR Region Selection** | Mouse-drag to select custom OCR recognition area |
| **Batch OCR** | Windows GPU (PaddleOCR 3.x) / macOS CPU (RapidOCR), auto-switching |
| **OCR Text Deduplication** | Prefix overlap, extension, suffix merge — reduces 45% redundancy |
| **AI Text Correction** | LLM API auto-fixes OCR errors, custom prompt templates supported |
| **Batch Processing** | Queue multiple videos, auto-skip failures |
| **One-Click Extract** | Frame extraction → region detection → OCR → AI correction, fully automated |
| **CJK Path Support** | Windows Chinese directory/filename compatibility (symlink + imencode fallback) |

## Download

Go to the [Releases](../../releases/latest) page:

| Platform | File | Description |
|----------|------|-------------|
| Windows | `KeyOCR_Setup.exe` | Installer (recommended), default install to `D:\KeyOCR` |
| Windows | `KeyOCR.exe` | Portable version |
| macOS | `KeyOCR-macOS.zip` | Unzip and double-click to run |

### Windows

1. Download `KeyOCR_Setup.exe`
2. Run installer, customize install directory if needed (English path recommended)
3. Launch from desktop shortcut

> **GPU Acceleration**: Requires NVIDIA GPU + CUDA 11.8 + cuDNN. Falls back to CPU OCR automatically when unavailable.

### macOS

1. Download `KeyOCR-macOS.zip`
2. Unzip and drag `KeyOCR.app` to Applications
3. If macOS says "cannot verify developer", right-click → Open

> macOS only supports CPU OCR (RapidOCR). No extra dependencies needed.

## Usage

### Basic Workflow

1. **Select Video** — Click "Select Video", supports multi-select (auto-enables batch mode)
2. **One-Click Extract** — Click "One-Click Extract", automatically:
   - Smart extraction: detect scene changes, extract keyframes
   - Region detection: auto-locate subtitle area (or manual selection)
   - Batch OCR: recognize text frame by frame
   - Text merge: deduplicate adjacent frame content
   - AI correction: fix OCR errors via LLM
3. **View Results** — Click "Open Folder" to see output

### Settings

Click the "Settings" button to configure:

- **API Settings** — API URL, Key, model name (required for AI correction)
- **OCR Engine** — Auto / Force CPU / Force GPU
- **OCR Region** — Auto detect / Manual selection
- **AI Prompt** — Custom correction template, use `{ocr_text}` as placeholder
- **Auto Cleanup** — Delete intermediate files after AI correction, keep only final result
- **Clear Cache** — Delete all intermediate frame images, keep final output

### Output

- Intermediate frames: `{install_dir}/cache/{video_name}_frames/`
- Final result: `{install_dir}/最终版/{video_name}-最终版.txt`

## Build from Source

```bash
git clone https://github.com/Ha1baraA11/KeyOCR.git
cd KeyOCR
```

### macOS (CPU)

```bash
pip install PySide6 opencv-contrib-python==4.10.0.84 numpy rapidocr-onnxruntime
python frame_extractor_gui.py
```

### Windows (GPU) — Full Setup Guide

#### Prerequisites

| Component | Version | Notes |
|-----------|---------|-------|
| Python | 3.10 or 3.12 | paddlepaddle-gpu does NOT support 3.13+ |
| NVIDIA GPU | Any with CUDA support | RTX 20/30/40 series recommended |
| CUDA Toolkit | 11.8 | Must match paddlepaddle-gpu build |
| cuDNN | 8.6+ for CUDA 11.8 | Required by PaddlePaddle |

#### Step 1: Install CUDA Toolkit 11.8

1. Go to [NVIDIA CUDA Toolkit Archive](https://developer.nvidia.com/cuda-toolkit-archive)
2. Select **CUDA Toolkit 11.8.0**
3. Choose your OS: **Windows → x86_64 → 10/11 → exe (local)**
4. Download the ~3 GB installer
5. Run the installer, select **Custom (Advanced)**
6. Make sure **CUDA > Development** and **CUDA > Runtime** are checked
7. Complete the installation

Verify installation:

```bash
nvcc --version
# Should output: Cuda compilation tools, release 11.8
```

> If `nvcc` is not found, add `C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v11.8\bin` to your system PATH.

#### Step 2: Install cuDNN

1. Go to [NVIDIA cuDNN Download](https://developer.nvidia.com/rdp/cudnn-archive) (requires free NVIDIA account)
2. Select **cuDNN v8.6.0 (or later) for CUDA 11.x**
3. Download the **Windows** zip
4. Extract and copy files to CUDA installation:
   - `bin\cudnn*.dll` → `C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v11.8\bin`
   - `include\cudnn*.h` → `C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v11.8\include`
   - `lib\x64\cudnn*.lib` → `C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v11.8\lib\x64`

#### Step 3: Install Python Dependencies

Open PowerShell or CMD and run each command in order:

```bash
# 1. Install Python (3.10 or 3.12, NOT 3.13+)
#    Download from https://www.python.org/downloads/
#    Check "Add Python to PATH" during installation

# 2. Remove conflicting OpenCV packages
python -m pip uninstall opencv-python opencv-contrib-python opencv-python-headless -y

# 3. Install OpenCV (must be contrib version, pinned to 4.10.0.84)
python -m pip install opencv-contrib-python==4.10.0.84

# 4. Install PaddlePaddle GPU (from PaddlePaddle official mirror, NOT PyPI)
python -m pip install paddlepaddle-gpu==3.3.0 -i https://www.paddlepaddle.org.cn/packages/stable/cu118/

# 5. Install PaddleOCR and PaddleX
python -m pip install paddleocr "paddlex[ocr]" pypdfium2

# 6. Install PaddleOCR runtime dependencies
python -m pip install pandas scipy scikit-image shapely pyclipper rapidfuzz lmdb pyyaml tqdm protobuf Pillow requests

# 7. Install GUI framework
python -m pip install PySide6 numpy
```

> **Important**: `paddlepaddle-gpu` is NOT on PyPI. You must use the PaddlePaddle official mirror (`-i https://www.paddlepaddle.org.cn/...`). Using `pip install paddlepaddle` from PyPI will install the CPU-only version.

#### Step 4: Run

```bash
python frame_extractor_gui.py
```

#### Step 5: Verify GPU is Working

In the app, go to Settings → OCR Engine → should show "GPU (PaddleOCR)" as available.

Or verify manually:

```bash
python -c "import paddle; print('CUDA:', paddle.device.is_compiled_with_cuda())"
# Should output: CUDA: True
```

### Windows (CPU, no GPU)

If you don't have an NVIDIA GPU, use the simpler CPU setup:

```bash
python -m pip install opencv-contrib-python==4.10.0.84 PySide6 numpy rapidocr-onnxruntime
python frame_extractor_gui.py
```

### Verify Environment

```bash
python -c "import cv2; print('cv2:', cv2.__version__)"
python -c "import paddle; print('paddle:', paddle.__version__, 'CUDA:', paddle.device.is_compiled_with_cuda())"
python -c "import paddleocr; import paddlex; print('paddleocr+paddlex OK')"
python -c "from rapidocr_onnxruntime import RapidOCR; print('rapidocr OK')"
```

## Windows Packaging

### Automatic (CI)

Push to main branch triggers GitHub Actions: build → self-check → create Release.

### Local Build

```bash
# Double-click build.bat or run manually:
python -m pip install pyinstaller
pyinstaller frame_extractor.spec
```

After packaging, self-check runs automatically (`KEYOCR_SELF_CHECK=1`), verifying EXE module integrity + CUDA availability.

### Generate Installer

After packaging, open `frame_extractor.iss` with Inno Setup to compile the installer.

## OCR Engines

| Engine | Platform | Dependencies | Notes |
|--------|----------|-------------|-------|
| PaddleOCR 3.x | Windows (CUDA) | `paddlepaddle-gpu` + `paddlex[ocr]` | GPU accelerated |
| RapidOCR | macOS / Windows CPU fallback | `rapidocr-onnxruntime` | CPU only |

Auto-detects CUDA at startup:
- Windows + CUDA available → PaddleOCR (GPU)
- Windows + CUDA unavailable → RapidOCR (CPU), logs the reason
- macOS → Always RapidOCR (CPU)

## Algorithm

### Smart Frame Extraction

Based on video scene change detection:

1. Sample at 9fps
2. Compute adjacent frame differences, detect peaks (diff > median × 1.5)
3. Take only 1 frame per peak to avoid redundancy

### OCR Region Detection

Sobel horizontal edge + voting mechanism:

1. Sample 16 frames from extracted set
2. Each frame independently detects subtitle region (Sobel edge → row clustering → top 2 clusters)
3. Vote for median, ensuring stability

### OCR Text Merge

Four merge strategies:
- **Prefix overlap**: Current frame is prefix of previous → skip
- **Extension**: Previous frame is prefix of current → replace with longer version
- **Common prefix**: Overlap > 50% → keep longest version
- **Suffix overlap**: Previous suffix = current prefix → concatenate into full sentence

## Project Structure

```
KeyOCR/
├── frame_extractor_gui.py    # Main app (GUI + algorithms + OCR + AI correction)
├── frame_extractor.spec      # PyInstaller build config
├── frame_extractor.iss       # Inno Setup installer script
├── runtime_hook_cv2.py       # PyInstaller runtime hook
├── build.bat                 # Windows local build script
├── detect_region.py          # Region detection standalone test
├── merge_ocr.py              # OCR result local merge/dedup script
├── run_test.py               # Test script
├── test_region_detect.py     # Region detection unit test
├── icon.ico                  # App icon
├── KeyOCR_logo.png           # Project logo
└── requirements.txt          # Python dependencies
```

## Troubleshooting

### GPU OCR not working

1. Check for NVIDIA GPU: `nvidia-smi`
2. Check CUDA 11.8 installed: `nvcc --version`
3. Check paddle is GPU version: `python -c "import paddle; print(paddle.device.is_compiled_with_cuda())"`
4. If output is False, reinstall: `python -m pip install paddlepaddle-gpu==3.3.0 -i https://www.paddlepaddle.org.cn/packages/stable/cu118/`

### PaddleX model cache corrupted

Clear cache and rerun:
- Windows: `rmdir /s /q C:\Users\{username}\.paddlex`
- macOS/Linux: `rm -rf ~/.paddlex`

### CJK path errors

The app has built-in CJK path support. If issues persist:
- Move video to an English path
- Or use the installer version (default install to `D:\KeyOCR`)

### AI correction not working

1. Verify API Key is set in Settings
2. Verify API URL is accessible
3. Check model name is correct

## Tech Stack

- **GUI**: PySide6 (Qt for Python)
- **Video Processing**: OpenCV
- **OCR**: PaddleOCR 3.x (GPU) / RapidOCR (CPU)
- **AI Correction**: OpenAI-compatible API (any compatible endpoint)
- **Packaging**: PyInstaller + Inno Setup

## License

MIT
