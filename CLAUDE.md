# CLAUDE.md - ZhenTiqu (帧提取工具)

## 快捷指令
- **`update`** — 用户说 "update" 时，自动执行：1) 更新 memory；2) 更新 CLAUDE.md；3) `git add . && git commit && git push` 推送到 GitHub。一次性完成，无需额外确认。

## 项目概述
视频分帧工具，基于 PySide6 GUI + OpenCV，从视频中智能提取关键帧并批量 OCR。

## 运行环境
- Python 3.13
- macOS ARM64
- 依赖：PySide6, opencv-python, numpy, rapidocr
- 启动命令：`python frame_extractor_gui.py`

## 项目结构
- `frame_extractor_gui.py` — 主程序（GUI + 所有算法 + 批量 OCR）
- `智能筛选算法迭代.md` — 完整的算法迭代过程记录
- `.claude/task.md` — 任务状态记录
- `.claude/test_results.md` — 测试结果记录

## GUI 按钮
1. **开始截帧** — 按固定帧率截取视频帧
2. **智能提取** — 基于转换点检测的智能提取（原"粗扫+精扫"）
3. **批量OCR** — 对输出目录中的图片批量 OCR，输出合并文本

## 核心算法

### 智能提取（SmartExtractWorker）
基于转换点检测，直接从视频提取关键帧：
1. 粗扫截帧（默认 9fps）
2. 检测转换峰值（next_diff > 中位数 × 1.5）
3. 提取峰值前的帧（默认 0.3s）

参数：`thresh_mult=1.5`, `min_dist_frames=7`, `pre_sec=0.3`（后两个硬编码）

### 批量 OCR（BatchOCRWorker）
使用 RapidOCR（PP-OCRv4, ONNX Runtime）逐张识别图片，结果合并输出到 `ocr_results.txt`。

## 测试结果（测试.mp4，4020帧，144秒）
- 智能提取：738 帧，覆盖率 97.3%，压缩率 18.4%（5.4x）
- 漏掉帧：frame_003594（距离最近峰值 15 帧，需增大 pre_sec 覆盖）

## 测试数据
- 测试视频：`/Users/zetazero/Downloads/测试.mp4`（4020帧，28fps，144秒）
- 测试视频2：`/Users/zetazero/Downloads/测试2.mp4`（13034帧，21fps，10.3分钟）
- 正确答案（37帧）：frame_000135 到 frame_004017，详见 `.claude/task.md`
