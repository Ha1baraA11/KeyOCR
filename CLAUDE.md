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
- `frame_extractor_gui.py` — 主程序（GUI + 所有算法 + 批量 OCR + 区域检测）
- `detect_region.py` — 独立的区域检测测试脚本
- `merge_ocr.py` — OCR 结果本地合并去重脚本
- `智能筛选算法迭代.md` — 完整的算法迭代过程记录
- `.claude/task.md` — 任务状态记录
- `.claude/test_results.md` — 测试结果记录

## GUI 按钮
1. **选择视频** — 选择视频文件，支持多选（多选自动开启批处理）
2. **一键提取** — 智能提取 + 区域检测/手动选择 + OCR + AI 纠错，全流程自动
3. **停止** — 中断当前任务（批处理模式下终止整个队列）
4. **设置** — API 配置、OCR 引擎、OCR 区域模式、清除缓存

## 批处理模式
- 选择多个视频时自动开启批处理
- 依次处理每个视频：智能提取 → 区域检测 → OCR → AI 纠错
- 失败的视频自动跳过，继续处理下一个
- 全部完成后输出总耗时，可打开最后输出目录

## 缓存管理
- 设置中"清除缓存"扫描用户主目录下所有 `_frames` 目录
- 删除除 `-最终版.txt` 以外的所有文件
- 跳过隐藏目录和系统目录（`.git`、`node_modules`、`Library`、`AppData`）

## 核心算法

### 智能提取（SmartExtractWorker）
基于转换点检测，直接从视频提取关键帧：
1. 粗扫截帧（默认 9fps）
2. 检测转换峰值（next_diff > 中位数 × 1.5）
3. 每个峰值只取峰值处的 1 帧

参数：`thresh_mult=1.5`, `min_dist_frames=5`（硬编码）

**优化记录**：
- 旧策略（pre=0.3s）：738 帧，覆盖率 97.3%，5.4x 压缩
- 新策略（每个峰值取 1 帧）：96 帧，覆盖率 97.3%，41.9x 压缩
- 帧数减少 87%，覆盖率不变

### 批量 OCR（BatchOCRWorker）
使用 RapidOCR（PP-OCRv4, ONNX Runtime）逐张识别图片，结果合并输出到 `ocr_results.txt`。

### OCR 本地合并去重（merge_ocr.py）
OCR 完成后自动调用，把相邻帧中重复的文本合并：
1. 前缀重叠：当前帧是前一帧的前缀 → 跳过
2. 扩展关系：前一帧是当前帧的前缀 → 用当前帧替换
3. 公共前缀：公共前缀超过较短文本的 50% → 保留最长版本
4. 后缀重叠：前一帧后缀 = 当前帧前缀 → 合并成一个句子

**效果**：测试2.mp4 从 321 帧合并到 175 条（减少 45%），再发给 AI 纠错。

### OCR 区域检测（detect_center_region）
自动检测帧中最大的纯色区域（背景杂乱，中间有纯色块如纸张/屏幕）：
1. 计算局部标准差（纯色区域标准差低）
2. Otsu 自适应阈值分离纯色和非纯色
3. 形态学清理，找最大轮廓
4. 逐行检查方差，精确裁剪上下边界
5. 宽度取全宽，返回相对比例坐标

### OCR 模式切换
GUI 设置中支持两种 OCR 区域模式：
- **自动 OCR**：粗扫完成后自动调用 detect_center_region 检测纯色区域
- **手动 OCR**：粗扫完成后弹出 RegionSelectorDialog 让用户手动框选

## 测试结果（测试.mp4，4020帧，144秒）
- 智能提取：738 帧，覆盖率 97.3%，压缩率 18.4%（5.4x）
- 漏掉帧：frame_003594（距离最近峰值 15 帧，需增大 pre_sec 覆盖）

## 测试数据
- 测试视频：`/Users/zetazero/Downloads/测试.mp4`（4020帧，28fps，144秒）
- 测试视频2：`/Users/zetazero/Downloads/测试2.mp4`（13034帧，21fps，10.3分钟）
- 测试视频3：`/Users/zetazero/Downloads/测试3.mp4`
- 正确答案（37帧）：frame_000135 到 frame_004017，详见 `.claude/task.md`

## OCR 区域检测测试结果
- 测试.mp4 (544x960): y=339, h=281, 29.3%
- 测试2.mp4 (480x854): y=299, h=256, 30.0%
- 测试3.mp4 (480x854): y=299, h=256, 30.0%
