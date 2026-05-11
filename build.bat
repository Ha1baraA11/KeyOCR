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
    echo [错误] 未找到 Python，请先安装 Python 3.10+
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

REM 检查 pip 是否可用
pip --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 pip
    pause
    exit /b 1
)

echo [1/4] 安装项目依赖...
pip install PySide6 opencv-python numpy -q
if errorlevel 1 (
    echo [错误] 依赖安装失败
    pause
    exit /b 1
)

echo [2/4] 安装 PaddleOCR（Windows 版）...
pip install paddlepaddle paddleocr -q
pip install "paddlex[ocr]" -q
if errorlevel 1 (
    echo [警告] PaddleOCR 安装失败，OCR 功能可能不可用
    echo         可稍后手动安装: pip install paddlepaddle paddleocr "paddlex[ocr]"
)

echo [3/4] 安装 PyInstaller...
pip install pyinstaller -q
if errorlevel 1 (
    echo [错误] PyInstaller 安装失败
    pause
    exit /b 1
)

echo [4/4] 开始打包...
echo.
pyinstaller frame_extractor.spec --clean --noconfirm
if errorlevel 1 (
    echo.
    echo [错误] 打包失败，请检查错误信息
    pause
    exit /b 1
)

echo.
echo ========================================
echo    打包完成！
echo ========================================
echo.
echo 可执行文件位置: dist\帧提取工具.exe
echo.
echo 提示:
echo - 首次运行可能需要几秒启动时间
echo - 如果杀毒软件误报，请添加信任
echo.
pause
