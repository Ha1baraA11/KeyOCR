@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ========================================
echo    帧提取工具 - Windows 打包脚本
echo ========================================
echo.

REM 检查 Python 是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.10 或 3.12
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [1/6] 检查 Python 版本...
for /f "tokens=2 delims= " %%i in ('python --version 2^>^&1') do set PYVER=%%i
echo 检测到 Python !PYVER!
echo !PYVER! | findstr "3.10 3.12" >nul
if errorlevel 1 (
    echo [错误] Windows GPU OCR 仅验证 Python 3.10 / 3.12
    pause
    exit /b 1
)

echo [2/6] 升级 pip...
python -m pip install --upgrade pip -q
if errorlevel 1 (
    echo [错误] pip 升级失败
    pause
    exit /b 1
)

echo [3/6] 清理冲突的 OpenCV 包...
python -m pip uninstall opencv-python opencv-contrib-python opencv-python-headless -y >nul 2>&1

echo [4/6] 安装基础依赖...
python -m pip install PySide6 numpy pyinstaller rapidocr-onnxruntime -q
if errorlevel 1 (
    echo [错误] 基础依赖安装失败
    pause
    exit /b 1
)
python -m pip install opencv-contrib-python==4.10.0.84 -q
if errorlevel 1 (
    echo [错误] OpenCV 安装失败
    pause
    exit /b 1
)

echo [5/6] 安装 PaddleOCR GPU 依赖...
echo 注意: paddlepaddle-gpu 需要百度源，如果网络问题可手动安装
python -m pip install paddlepaddle-gpu==3.3.0 -i https://mirror.baidu.com/pypi/simple -q
if errorlevel 1 (
    echo [错误] paddlepaddle-gpu 安装失败，停止打包
    echo 不能继续回退到 CPU 版 paddle，否则会打出一个看起来像 GPU 版、实际不能用 CUDA 的安装包
    pause
    exit /b 1
)
python -m pip install paddleocr "paddlex[ocr]" pypdfium2 -q
if errorlevel 1 (
    echo [错误] PaddleOCR 核心依赖安装失败
    echo 请确认 NVIDIA 驱动 591.86+、CUDA 11.8、cuDNN 已安装
    pause
    exit /b 1
)
python -c "import paddle; print('paddle:', paddle.__version__, 'CUDA:', paddle.device.is_compiled_with_cuda()); assert paddle.device.is_compiled_with_cuda(), '当前安装的不是 GPU 版 paddle，停止打包'"
if errorlevel 1 (
    echo [错误] 当前安装的 paddle 不是 GPU 版，停止打包
    pause
    exit /b 1
)
python -m pip install pandas scipy scikit-image shapely pyclipper rapidfuzz lmdb pyyaml tqdm protobuf Pillow requests -q
if errorlevel 1 (
    echo [错误] PaddleOCR 传递依赖安装失败
    pause
    exit /b 1
)

echo [6/6] 开始打包...
echo.
python -m PyInstaller frame_extractor.spec --clean --noconfirm
if errorlevel 1 (
    echo.
    echo [错误] 打包失败，请检查错误信息
    pause
    exit /b 1
)

echo [附加检查] 验证打包后的 EXE 依赖完整性...
set ZHENTIQU_SELF_CHECK=1
set ZHENTIQU_SELF_CHECK_OUTPUT=%TEMP%\zhentiqu-self-check.json
dist\帧提取工具.exe
if errorlevel 1 (
    echo [错误] 打包后的 EXE 自检失败
    if exist "%ZHENTIQU_SELF_CHECK_OUTPUT%" type "%ZHENTIQU_SELF_CHECK_OUTPUT%"
    pause
    exit /b 1
)
if exist "%ZHENTIQU_SELF_CHECK_OUTPUT%" (
    echo 自检报告:
    type "%ZHENTIQU_SELF_CHECK_OUTPUT%"
)
set ZHENTIQU_SELF_CHECK=
set ZHENTIQU_SELF_CHECK_OUTPUT=

echo.
echo ========================================
echo    打包完成！
echo ========================================
echo.
echo 可执行文件位置: dist\帧提取工具.exe
echo.
echo 提示:
echo - 首次运行 OCR 可能会下载模型，时间较长
echo - 如果 OCR 初始化失败，请先删除 %USERPROFILE%\.paddlex 后重试
echo - 如果杀毒软件误报，请添加信任
echo.
pause
