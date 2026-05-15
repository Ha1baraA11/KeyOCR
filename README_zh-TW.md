# KeyOCR

影片智慧分幀 + OCR 文字提取工具。基於 PySide6 GUI + OpenCV，從影片中自動提取關鍵幀並批次辨識文字。

[English](README.md) | [简体中文](README_zh-CN.md)

## 功能

- **智慧分幀** — 場景轉換點偵測，自動提取關鍵幀，14x 壓縮率
- **自動 OCR 區域偵測** — Sobel 邊緣 + 投票機制，自動定位字幕區域
- **批次 OCR** — Windows GPU (PaddleOCR 3.x) / macOS CPU (RapidOCR)，自動切換
- **OCR 文字合併去重** — 相鄰幀重複文字自動合併，減少 45% 冗餘
- **AI 文字糾錯** — 呼叫大模型 API 自動修正 OCR 錯誤
- **批次處理** — 多個影片排隊處理，失敗自動跳過
- **一鍵提取** — 分幀 → 區域偵測 → OCR → AI 糾錯，全流程自動

## 下載

前往 [Releases](../../releases/latest) 頁面下載：

| 平台 | 檔案 | 說明 |
|------|------|------|
| Windows | `KeyOCR_Setup.exe` | 安裝程式（推薦） |
| Windows | `KeyOCR.exe` | 便攜版 |
| macOS | `KeyOCR-macOS.zip` | 解壓後雙擊執行 |

### Windows 使用者

下載 `KeyOCR_Setup.exe`，安裝後雙擊執行。

GPU 加速需 NVIDIA 顯示卡 + CUDA 11.8。無顯示卡時自動使用 CPU OCR。

### macOS 使用者

下載 `KeyOCR-macOS.zip`，解壓後將 `KeyOCR.app` 拖入 Applications 資料夾。

首次執行如提示「無法驗證開發者」，右鍵 → 打開 即可。

## 從原始碼執行

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

## 專案結構

| 檔案 | 說明 |
|------|------|
| `frame_extractor_gui.py` | 主程式（GUI + 所有演算法 + 批次 OCR + 區域偵測） |
| `frame_extractor.spec` | PyInstaller 打包設定 |
| `frame_extractor.iss` | Inno Setup 安裝程式腳本 |
| `runtime_hook_cv2.py` | PyInstaller runtime hook |
| `build.bat` | Windows 本機打包腳本 |
| `detect_region.py` | 區域偵測測試腳本 |
| `merge_ocr.py` | OCR 結果合併去重腳本 |
| `run_test.py` | 測試腳本 |
| `智能筛选算法迭代.md` | 演算法迭代過程紀錄 |

## OCR 引擎

| 引擎 | 平台 | 依賴 |
|------|------|------|
| PaddleOCR 3.x | Windows (CUDA) | `paddlepaddle-gpu` + `paddlex[ocr]` |
| RapidOCR | macOS / Windows CPU 回退 | `rapidocr-onnxruntime` |

程式自動偵測 CUDA 可用性，不可用時自動回退到 CPU OCR。

## 設定

設定儲存在程式同目錄的 `config.json`，支援設定：

- **API 設定** — API URL、Key、模型名稱
- **OCR 引擎** — 自動 / 強制 CPU / 強制 GPU
- **OCR 區域** — 自動偵測 / 手動框選
- **AI 提示詞** — 自訂糾錯範本，`{ocr_text}` 為佔位符
- **自動清理** — AI 糾錯後自動刪除中間檔案

## License

MIT
