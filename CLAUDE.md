# CLAUDE.md - KeyOCR (帧提取工具)

## 快捷指令
- **`update`** — 用户说 "update" 时，自动执行：1) 更新 memory；2) 更新 CLAUDE.md；3) `git add . && git commit && git push` 推送到 GitHub。一次性完成，无需额外确认。

## 项目概述
视频分帧工具，基于 PySide6 GUI + OpenCV，从视频中智能提取关键帧并批量 OCR。

## 运行环境
- Python 3.12+（Windows GPU 需 3.9~3.12，CI 用 3.12）
- macOS ARM64 / Windows x64
- 启动命令：`python frame_extractor_gui.py`

### macOS 依赖（CPU）
```
pip install PySide6 opencv-contrib-python==4.10.0.84 numpy rapidocr-onnxruntime
```

### Windows 依赖版本清单（GPU）

**已验证的环境**（RTX 3070 8GB）
| 组件 | 版本 |
|------|------|
| GPU 驱动 | 591.86 |
| CUDA Toolkit (nvcc) | 11.8.89 |
| nvidia-smi 最高支持 CUDA | 13.1 |
| Python | 3.12.10 |
| paddle | 3.3.0 |
| opencv-contrib-python | 4.10.0 |
| paddleocr | 3.x (OK) |
| paddlex | OK |
| PySide6 | OK |

**核心依赖**
| 包名 | 版本 | 说明 |
|------|------|------|
| Python | 3.10 / 3.12 | paddlepaddle-gpu 不支持 3.13+ |
| opencv-contrib-python | ==4.10.0.84 | 不能用 opencv-python（与 paddleocr 冲突）；4.13.0 太新，PaddleX image_reader.py 报 NameError |
| paddlepaddle-gpu | 3.3.0 | 需 CUDA 11.8 + cuDNN |
| paddleocr | 3.x | 3.x API：`use_textline_orientation=True`，`predict()` 返回字典 |
| paddlex[ocr] | latest | 必须装完整 `[ocr]` extra，不能只装 `[ocr-core]`（上游依赖声明 bug） |
| pypdfium2 | latest | paddlex 依赖 |
| PySide6 | latest | |
| numpy | latest | |

**传递依赖**（paddleocr/paddlex 运行时需要，pip 可能不自动装全）
```
pandas scipy scikit-image shapely pyclipper rapidfuzz lmdb pyyaml tqdm protobuf Pillow requests
```

**paddlex[ocr] extra 依赖**（spec hidden_imports 需覆盖）
```
safetensors tokenizers sentencepiece tiktoken einops regex ftfy imagesize Jinja2 lxml openpyxl pypdfium2 python_bidi latex2mathml premailer
```

**paddlex[ocr] core 依赖**
```
aistudio_sdk modelscope huggingface_hub ujson colorlog pydantic ruamel.yaml
```

**可选（CPU 模式）**
| 包名 | 说明 |
|------|------|
| rapidocr-onnxruntime | macOS CPU OCR；import 名可能是 `rapidocr` 或 `rapidocr_onnxruntime` |

### 一键安装命令（Windows）
```
python -m pip uninstall opencv-python opencv-contrib-python opencv-python-headless -y
python -m pip install opencv-contrib-python==4.10.0.84
python -m pip install paddlepaddle-gpu==3.3.0 -i https://www.paddlepaddle.org.cn/packages/stable/cu118/
python -m pip install paddleocr "paddlex[ocr]" pypdfium2
python -m pip install pandas scipy scikit-image shapely pyclipper rapidfuzz lmdb pyyaml tqdm protobuf Pillow requests
python -m pip install PySide6 numpy pyinstaller
```

**注意**：`paddlepaddle-gpu` 不在 PyPI 上，必须用 PaddlePaddle 官方镜像安装：
- CUDA 11.8：`-i https://www.paddlepaddle.org.cn/packages/stable/cu118/`
- CUDA 12.6：`-i https://www.paddlepaddle.org.cn/packages/stable/cu126/`
- PyPI 上只有 `paddlepaddle`（CPU 版）

### 环境检测命令
```
python -c "import cv2; print('cv2:', cv2.__version__)"
python -c "import paddle; print('paddle:', paddle.__version__, 'CUDA:', paddle.device.is_compiled_with_cuda())"
python -c "import paddleocr; import paddlex; print('paddleocr+paddlex OK')"
python -c "from rapidocr_onnxruntime import RapidOCR; print('rapidocr OK')"
```

### 注意事项
- Windows 上 `pip` 可能不在 PATH，用 `python -m pip` 代替
- PaddleX 模型缓存损坏时清除：`rmdir /s /q C:\Users\{用户名}\.paddlex`

## Windows 中文路径兼容
OpenCV 在 Windows 上不支持非 ASCII 路径（中文目录/文件名）。代码通过以下方式兼容：
- **读写帧图片**：`cv2.imwrite`/`cv2.imread` 失败时回退到 `cv2.imencode`/`cv2.imdecode` + Python 原生文件 IO
- **打开视频文件**：`_safe_open_path()` 在 temp 目录创建符号链接（不复制文件），`cv2.VideoCapture` 通过链接访问
- **PaddleOCR**：单例模式 + 文件顶部预导入（避免 PaddleX 重复初始化），失败时自动 fallback 到 RapidOCR

## Windows 打包与安装
- `pyinstaller frame_extractor.spec` 生成 exe（icon.ico 打入包内）
- spec 用 `_collect_required_submodules` 自动发现 paddle/paddleocr/paddlex 全部子模块（失败直接 SystemExit，不静默跳过）
- spec 用 `_collect_required_assets` 收集原生二进制 + 数据文件（`copy_metadata` 失败降为警告）
- spec 还必须收 `rapidocr` / `rapidocr_onnxruntime` 的 yaml/onnx/txt 资源，否则 CPU OCR 会报 `_MEI...\\rapidocr_onnxruntime\\config.yaml` 不存在
- CI 和 build.bat 打包后都运行自检（`KEYOCR_SELF_CHECK=1`），验证 EXE 内模块完整性 + CUDA 可用
- CI 用 `paddlepaddle-gpu==3.3.0`（百度源），`assert paddle.device.is_compiled_with_cuda()` 验证
- build.bat 同样要求 GPU 版 paddle，安装失败直接停止（不回退 CPU 版）
- spec 的 hidden_imports 包含 paddlex[ocr] 的全部依赖（core + extra，共 23 个包）
- `frame_extractor.iss` — Inno Setup 安装脚本，默认装到 `D:\KeyOCR`（英文路径，避免中文路径和 Program Files 权限问题），支持自定义目录、桌面快捷方式
- 安装后配置和缓存都在安装目录下（`config.json` 和 `cache/`）
- `{app}` 和 `{app}\cache` 都设了 `users-modify` 权限（兜底 Program Files 场景）
- **GitHub Actions CI**：push 到 main 自动构建 → 自检 → 创建 Release（`.github/workflows/build.yml`）
- `build.bat` — Windows 本地打包脚本（双击运行）

## 窗口图标
- `icon.ico` 同时用于 exe 文件图标和窗口标题栏图标
- 运行时通过 `sys._MEIPASS`（打包后）或脚本目录（开发时）定位图标文件

## 项目结构
- `frame_extractor_gui.py` — 主程序（GUI + 所有算法 + 批量 OCR + 区域检测）
- `frame_extractor.spec` — PyInstaller 打包配置（含 icon.ico 打包 + fail-fast 资产收集）
- `frame_extractor.iss` — Inno Setup 安装程序脚本
- `runtime_hook_cv2.py` — PyInstaller runtime hook，预导入 cv2
- `icon.ico` — 应用图标（窗口标题栏 + exe 文件图标）
- `detect_region.py` — 独立的区域检测测试脚本
- `merge_ocr.py` — OCR 结果本地合并去重脚本
- `智能筛选算法迭代.md` — 完整的算法迭代过程记录
- `AGENTS.md` — Codex/Claude agent 指令文件
- `.claude/task.md` — 任务状态记录
- `.claude/test_results.md` — 测试结果记录

## GUI 按钮
1. **选择视频** — 选择视频文件，支持多选（多选自动开启批处理）
2. **一键提取** — 智能提取 + 区域检测/手动选择 + OCR + AI 纠错，全流程自动
3. **停止** — 中断当前任务（批处理模式下终止整个队列）
4. **打开文件夹** — 打开 `最终版/` 输出文件夹
5. **设置** — API 配置、OCR 引擎、OCR 区域模式、AI 提示词模板、自动清理、清除缓存

## 设置持久化
- 配置存放在 exe 同目录的 `config.json`，JSON 格式
- 启动时自动加载，点"保存"时自动写入
- 开发环境和打包后行为一致
- API Key 默认为空，用户需在设置中填写
- AI 提示词模板可在设置中编辑，使用 `{ocr_text}` 作为 OCR 文本占位符

## 输出目录
- 提取的帧统一存放在 `{安装目录}/cache/{视频名}_frames/`
- AI 纠错完成后，`{视频名}-最终版.txt` 自动复制到 `{安装目录}/最终版/`
- 清除缓存只扫描 `{安装目录}/cache/` 目录

## OCR 引擎
- **自动选择**：macOS 用 RapidOCR (CPU)，Windows 优先 PaddleOCR (GPU)，CUDA 不可用时自动 fallback 到 RapidOCR (CPU) 并提示原因
- **CPU (RapidOCR)**：纯 CPU，无需额外环境。import 兼容 `rapidocr` 和 `rapidocr_onnxruntime` 两种包名（`pip install rapidocr-onnxruntime`）
- **GPU (PaddleOCR 3.x)**：需 CUDA + paddlepaddle-gpu + `pip install "paddlex[ocr]"`，CUDA 不可用时 fallback 到 RapidOCR
- PaddleOCR 3.x API：构造函数 `use_textline_orientation=True`，`predict()` 返回 OCRResult 字典（`rec_texts`/`rec_scores`）
- 文件顶部 `import paddle` + `import paddleocr` 预导入，避免 PaddleX 重复初始化
- OCR 开始时日志输出当前使用的引擎名称
- **自检机制**：`run_self_check()` 验证打包后 EXE 的依赖完整性，Windows 上还检查 `paddle_cuda=True`，通过 `KEYOCR_SELF_CHECK=1` 环境变量触发
- CI 和 build.bat 都在 PyInstaller 打包后运行自检，失败则中止发布
- **构建要求**：打包必须用 `paddlepaddle-gpu`（百度源），不能用 CPU 版 paddle，否则用户拿到的 EXE 不支持 CUDA

### 已踩坑与修复（Windows GPU OCR 全链路）

1. **PyInstaller 窗口模式 `sys.stdout`/`sys.stderr` 为 None**
   - 现象：PaddleX 模型下载进度 `print()` 报 `AttributeError: 'NoneType' object has no attribute 'write'`，导致模型下载中断，上层报 "No model source is available"
   - 修复：文件顶部 `import io`，检测 None 后补 `io.StringIO()` 空流

2. **PaddleX `require_extra`/`require_deps` 元数据误报 `DependencyError`**
   - 现象：`paddlex.utils.deps.DependencyError: PDFReaderBackend is not ready... opencv-contrib-python pypdfium2`
   - 原因：PaddleX 通过 `importlib.metadata` 检查包名，PyInstaller 打包后 `.dist-info` 丢失；开发环境下 `opencv-contrib-python` 与 `opencv-python` 包名冲突也会误报
   - 修复：`PaddleOCREngine.__init__` 同时 monkey-patch `require_extra` 和 `require_deps`，冻结和开发环境都跳过

3. **RapidOCR import 名与 PyPI 包名不一致**
   - 现象：`ModuleNotFoundError: No module named 'rapidocr'`
   - 原因：PyPI 包名 `rapidocr-onnxruntime`，但 import 名可能是 `rapidocr` 或 `rapidocr_onnxruntime`
   - 修复：`RapidOCREngine.__init__` 和 `_check_rapidocr` 都加了 try/except fallback

4. **opencv-contrib-python 版本兼容**
   - PaddleOCR 需要 `opencv-contrib-python`（不是 `opencv-python`），两者冲突不能共存
   - `opencv-contrib-python` 4.13.0 太新，PaddleX 内部 `image_reader.py` 报 `NameError: name 'cv2' is not defined`
   - 需降级到 `opencv-contrib-python==4.10.0.84`

5. **PaddleX 模型缓存损坏**
   - 首次下载因 stdout 崩溃中断后，`~/.paddlex/` 可能留下残缺模型文件
   - 清除方法：`rmdir /s /q C:\Users\{用户名}\.paddlex`（Windows）或 `rm -rf ~/.paddlex`（macOS/Linux）

6. **Windows 上 `pip` 不在 PATH**
   - 用 `python -m pip install ...` 代替 `pip install ...`

7. **PaddleX `is_dep_available` 导致 `image_reader.py` 不导入 cv2**
   - 现象：PyInstaller 打包后 `NameError: name 'cv2' is not defined`（`image_reader.py` line 41）
   - 原因：PaddleX `image_reader.py` 用 `is_dep_available("opencv-contrib-python")` 判断是否 `import cv2`，PyInstaller 打包后元数据丢失返回 False，cv2 未导入
   - 修复：`PaddleOCREngine.__init__` 中 patch `is_dep_available`，对 `opencv-contrib-python`/`opencv-python` 返回 True

8. **GitHub Release 可能发出“假 GPU 包”**
   - 现象：用户机器有 CUDA / `nvcc --version` 正常，但程序仍报“当前环境未检测到可用 CUDA”
   - 根因：安装包内置的是 CPU 版 `paddlepaddle`，而不是 `paddlepaddle-gpu`
   - 修复：CI / `build.bat` 强制安装 GPU 版 paddle，并在打包前后双重校验 `compiled_with_cuda=True`

9. **RapidOCR 资源文件漏打包**
   - 现象：CPU OCR 或 GPU 失败后的回退 OCR 报 `FileNotFoundError: ...\\rapidocr_onnxruntime\\config.yaml`
   - 根因：spec 之前只收 Python 模块，没收 RapidOCR 的 yaml/onnx/txt 资源
   - 修复：spec 额外收集 `rapidocr` / `rapidocr_onnxruntime` 的 `collect_data_files` / `collect_dynamic_libs` / metadata

10. **PaddleX frozen 环境下 `cv2` 仍可能未定义**
   - 现象：GPU OCR 报 `NameError: name 'cv2' is not defined`，堆栈在 `paddlex.inference.common.reader.image_reader`
   - 根因：即使 patch 了 `is_dep_available`，frozen 环境里第三方模块的条件导入顺序仍可能不稳定
   - 修复：`runtime_hook_cv2.py` 注入 `builtins.cv2`，并在 `PaddleOCREngine.__init__` 中手动把 `cv2` 填回 `image_reader` 模块命名空间

11. **PaddleX 在 `predict()` 阶段仍会报 `_cv2_resize` 依赖缺失**
   - 现象：GPU OCR 初始化通过，但真正开始识别时又报 `DependencyError: _cv2_resize is not ready for use`
   - 根因：PaddleX 运行期会再次调用 `require_deps()`；只 patch 初始化阶段不够
   - 修复：增加 `_PaddleXDepsPatch` 上下文管理器，同时包裹 `paddleocr.PaddleOCR(...)` 初始化和 `self._engine.predict(...)` 调用

12. **RapidOCR 返回格式不稳定**
   - 现象：CPU OCR 报 `'tuple' object has no attribute 'txts'`
   - 根因：不同版本/打包形态下，RapidOCR 既可能返回对象（`txts`/`scores`），也可能返回 tuple（如 `(boxes, txts, scores)`）
   - 修复：`RapidOCREngine.ocr()` 同时兼容对象版与 tuple 版；score 缺失时允许按 `0.0` 继续

13. **PaddleX 文本检测阶段 `pyclipper` 未定义**
   - 现象：GPU OCR 报 `NameError: name 'pyclipper' is not defined`，堆栈在 `paddlex.inference.models.text_detection.processors`
   - 根因：`pyclipper` 与 `cv2` 一样，在 frozen 环境里条件导入可能未生效
   - 修复：`_PaddleXDepsPatch` 同时注入 `builtins.pyclipper`，并把 `pyclipper` 手动回填到 `text_detection.processors` 模块命名空间

14. **RapidOCR 可能返回嵌套列表**
   - 现象：CPU OCR 报 `sequence item 0: expected str instance, list found`
   - 根因：返回值中的 `txts` / `scores` 不一定是一维数组，可能出现嵌套 list
   - 修复：增加 `_normalize_text_items()` / `_normalize_score_items()`，统一把 OCR 结果压平成 `list[str]` / `list[float]`


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
