# CLAUDE.md - ZhenTiqu (帧提取工具)

## 快捷指令
- **`update`** — 用户说 "update" 时，自动执行：1) 更新 memory；2) 更新 CLAUDE.md；3) `git add . && git commit && git push` 推送到 GitHub。一次性完成，无需额外确认。

## 项目概述
视频分帧工具，基于 PySide6 GUI + OpenCV，从视频中智能提取关键帧并批量 OCR。

## 运行环境
- Python 3.12+（Windows GPU 需 3.9~3.12）
- macOS ARM64 / Windows x64
- 依赖：PySide6, opencv-python, numpy
- OCR：macOS 用 RapidOCR (CPU)，Windows 用 PaddleOCR (GPU 需 CUDA 11.8 + cuDNN + pandas)
- 启动命令：`python frame_extractor_gui.py`

## Windows 中文路径兼容
OpenCV 在 Windows 上不支持非 ASCII 路径（中文目录/文件名）。代码通过以下方式兼容：
- **读写帧图片**：`cv2.imwrite`/`cv2.imread` 失败时回退到 `cv2.imencode`/`cv2.imdecode` + Python 原生文件 IO
- **打开视频文件**：`_safe_open_path()` 在 temp 目录创建符号链接（不复制文件），`cv2.VideoCapture` 通过链接访问
- **PaddleOCR**：单例模式 + 文件顶部预导入（避免 PaddleX 重复初始化），失败时抛出完整错误（含 traceback），不静默降级

## Windows 打包与安装
- `pyinstaller frame_extractor.spec` 生成 exe（icon.ico 打入包内）
- spec 用 `collect_submodules` 自动发现 paddle/paddleocr/paddlex 全部子模块
- spec 用 `collect_dynamic_libs` + `collect_data_files` 收集原生二进制和数据文件（PyInstaller 6.x 移除了 `collect_binaries`）
- spec 用 `copy_metadata` 打入 paddlex/paddleocr/paddle 的包元数据
- CI 显式安装 paddleocr 全部传递依赖 + `paddlex[ocr]`
- `build.bat` 本地打包也安装 `paddlex[ocr]`
- spec 的 hidden_imports 包含 paddlex[ocr] 的全部依赖（core + extra，共 23 个包）
- `frame_extractor.iss` — Inno Setup 安装脚本，支持选目录、桌面快捷方式
- 安装后配置和缓存都在安装目录下（`config.json` 和 `cache/`）
- **GitHub Actions CI**：push 到 main 自动构建，产物：exe + 安装程序（`.github/workflows/build.yml`）
- `build.bat` — Windows 本地打包脚本（双击运行）

## 窗口图标
- `icon.ico` 同时用于 exe 文件图标和窗口标题栏图标
- 运行时通过 `sys._MEIPASS`（打包后）或脚本目录（开发时）定位图标文件

## 项目结构
- `frame_extractor_gui.py` — 主程序（GUI + 所有算法 + 批量 OCR + 区域检测）
- `frame_extractor.spec` — PyInstaller 打包配置（含 icon.ico 打包）
- `frame_extractor.iss` — Inno Setup 安装程序脚本
- `icon.ico` — 应用图标（窗口标题栏 + exe 文件图标）
- `detect_region.py` — 独立的区域检测测试脚本
- `merge_ocr.py` — OCR 结果本地合并去重脚本
- `智能筛选算法迭代.md` — 完整的算法迭代过程记录
- `.claude/task.md` — 任务状态记录
- `.claude/test_results.md` — 测试结果记录

## GUI 按钮
1. **选择视频** — 选择视频文件，支持多选（多选自动开启批处理）
2. **一键提取** — 智能提取 + 区域检测/手动选择 + OCR + AI 纠错，全流程自动
3. **停止** — 中断当前任务（批处理模式下终止整个队列）
4. **设置** — API 配置、OCR 引擎、OCR 区域模式、自动清理、清除缓存

## 设置持久化
- 配置存放在 exe 同目录的 `config.json`，JSON 格式
- 启动时自动加载，点"保存"时自动写入
- 开发环境和打包后行为一致
- API Key 默认为空，用户需在设置中填写

## 输出目录
- 提取的帧统一存放在 `{安装目录}/cache/{视频名}_frames/`
- 清除缓存只扫描 `{安装目录}/cache/` 目录

## OCR 引擎
- **自动选择**：macOS 用 RapidOCR (CPU)，Windows 用 PaddleOCR
- **CPU (RapidOCR)**：纯 CPU，无需额外环境
- **GPU (PaddleOCR 3.x)**：需 CUDA 11.8 + cuDNN + paddlepaddle-gpu + `pip install "paddlex[ocr]"`（PaddleX OCR pipeline 依赖），失败时展示完整错误日志
- PaddleOCR 3.x API：构造函数 `use_textline_orientation=True`，`predict()` 返回 OCRResult 字典（`rec_texts`/`rec_scores`）
- 文件顶部 `import paddle` + `import paddleocr` 预导入，避免 PaddleX 重复初始化
- OCR 开始时日志输出当前使用的引擎名称
- **PyInstaller 打包兼容**：exe 里 `importlib.metadata` 读不到 paddlex 的 extra 元数据，`PaddleOCREngine.__init__` 检测 `sys.frozen` 后 monkey-patch 跳过 `require_extra` 检查

## 批处理模式
- 选择多个视频时自动开启批处理
- 依次处理每个视频：智能提取 → 区域检测 → OCR → AI 纠错
- 失败的视频自动跳过，继续处理下一个
- 全部完成后输出总耗时，可打开最后输出目录

## 缓存管理
- 设置中"清除缓存"扫描 `{安装目录}/cache/` 下所有 `_frames` 目录
- 删除除 `-最终版.txt` 以外的所有文件
- **自动清理**：设置中开启后，AI 纠错完成自动删除当前视频的中间文件，只保留 `-最终版.txt`

## 核心算法

### 智能提取（SmartExtractWorker）
基于转换点检测，直接从视频提取关键帧：
1. 粗扫截帧（默认 9fps）
2. 检测转换峰值（next_diff > 中位数 × 1.5）
3. 每个峰值只取峰值处的 1 帧

参数：`thresh_mult=1.5`, `min_dist_frames=5`（硬编码）

**测试结果**（测试1.mp4，4020帧，144秒）：
- 96 帧，覆盖率 100%，压缩率 7.2%（14.0x）

### 批量 OCR（BatchOCRWorker）
逐张识别图片，结果合并输出到 `ocr_results.txt`。
- CPU 模式：RapidOCR（PP-OCRv4, ONNX Runtime）
- GPU 模式：PaddleOCR 3.x（PaddlePaddle + CUDA，`predict()` 返回 OCRResult 字典）

### OCR 本地合并去重（merge_ocr.py）
OCR 完成后自动调用，把相邻帧中重复的文本合并：
1. 前缀重叠：当前帧是前一帧的前缀 → 跳过
2. 扩展关系：前一帧是当前帧的前缀 → 用当前帧替换
3. 公共前缀：公共前缀超过较短文本的 50% → 保留最长版本
4. 后缀重叠：前一帧后缀 = 当前帧前缀 → 合并成一个句子

**效果**：测试2.mp4 从 321 帧合并到 175 条（减少 45%），再发给 AI 纠错。

### OCR 区域检测（detect_stable_region）
Sobel 水平边缘 + 投票机制。智能提取完成后检测一次，全部帧用同一区域。

单帧检测（detect_center_region）：
1. Sobel 水平边缘，计算每行宽度比（横跨 ≥50% 画面宽度的边缘行）
2. 聚类边缘行（间距 <10px），按宽度比×边缘强度排序
3. 取最强两个聚类作为上下边界

投票机制（detect_stable_region）：
1. 从 selected 目录采样 16 帧
2. 每帧单独检测，过滤 5%-50% 的有效结果
3. 按 y 值聚类（间距 <10%），选最大组的中位数

### OCR 模式切换
- **自动 OCR**：智能提取完成后，从 selected 帧投票检测区域
- **手动 OCR**：智能提取完成后，弹出 RegionSelectorDialog 用户框选

## 测试结果（测试1.mp4，4020帧，144秒）
- 智能提取：96 帧，覆盖率 100%，压缩率 7.2%（14.0x）
- 正确答案（37帧）全部命中，0 漏掉

## 测试数据
- 测试视频1：`/Users/zetazero/Downloads/测试1.mp4`（4020帧，28fps，144秒）
- 测试视频2：`/Users/zetazero/Downloads/测试2.mp4`（13034帧，21fps，10.3分钟）
- 测试视频3：`/Users/zetazero/Downloads/测试3.mp4`
- 测试视频4：`/Users/zetazero/Downloads/测试4.MP4`
- 正确答案（37帧）：frame_000135 到 frame_004017，详见 `.claude/task.md`

## OCR 区域检测测试结果
- 测试1 (544x960): y=330, h=299, 31.1%
- 测试2 (480x854): y=290, h=272, 31.9%
- 测试3 (480x854): y=290, h=272, 31.9%
- 测试4 (480x854): y=290, h=272, 31.9%
