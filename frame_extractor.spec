# -*- mode: python ; coding: utf-8 -*-
import sys
import os

block_cipher = None


def _collect_required_submodules(pkg, collect_submodules):
    try:
        modules = collect_submodules(pkg)
    except Exception as e:
        raise SystemExit(f"[spec] ERROR: collect_submodules({pkg!r}) failed: {e}")
    if not modules:
        raise SystemExit(f"[spec] ERROR: package {pkg!r} is not importable in the build environment")
    return modules


def _collect_required_assets(pkg, collect_dynamic_libs, collect_data_files, copy_metadata):
    try:
        binaries = collect_dynamic_libs(pkg)
        datas = collect_data_files(pkg, include_py_files=False)
    except Exception as e:
        raise SystemExit(f"[spec] ERROR: failed to collect assets for {pkg!r}: {e}")
    # copy_metadata 可能因 dist-info 名称不匹配而失败（如 paddlepaddle → paddle），非致命
    try:
        datas += copy_metadata(pkg)
    except Exception as e:
        print(f"[spec] WARNING: copy_metadata({pkg!r}) failed: {e}")
    return binaries, datas

# 隐式导入列表
hidden_imports = [
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
    'PySide6.QtSvg',
    'PySide6.QtSvgWidgets',
    'cv2',
    'numpy',
]

# Windows 特有依赖：自动收集 paddle/paddleocr/paddlex 全部子模块
if sys.platform == 'win32':
    from PyInstaller.utils.hooks import collect_submodules

    # 自动发现所有子模块，比手动列举可靠
    for pkg in ['paddle', 'paddleocr', 'paddlex']:
        hidden_imports.extend(_collect_required_submodules(pkg, collect_submodules))

    # 显式补充 PyInstaller 可能遗漏的关键模块
    hidden_imports.extend([
        'requests',
        'pandas',
        'PIL',
        'PIL.Image',
        'google.protobuf',
        'google.protobuf.descriptor',
        'google.protobuf.internal',
        'google.protobuf.message',
        'shapely',
        'pyclipper',
        'rapidfuzz',
        'lmdb',
        'skimage',
        'skimage.io',
        'skimage.transform',
        'scipy',
        'scipy.special',
        'scipy.spatial',
        'scipy.ndimage',
        'pyyaml',
        'yaml',
        'tqdm',
        # paddlex[ocr] 核心依赖
        'aistudio_sdk',
        'modelscope',
        'huggingface_hub',
        'ujson',
        'colorlog',
        'pydantic',
        'ruamel.yaml',
        # paddlex[ocr] extra 依赖
        'safetensors',
        'tokenizers',
        'sentencepiece',
        'tiktoken',
        'einops',
        'regex',
        'ftfy',
        'imagesize',
        'Jinja2',
        'lxml',
        'openpyxl',
        'pypdfium2',
        'python_bidi',
        'latex2mathml',
        'premailer',
        # RapidOCR（PaddleOCR 失败时的 fallback）
        'rapidocr',
        'rapidocr_onnxruntime',
        # OCR 合并去重
        'merge_ocr',
    ])

else:
    hidden_imports.extend([
        'rapidocr',
        'rapidocr_onnxruntime',
    ])

# 收集原生二进制和数据文件
extra_binaries = []
extra_datas = []
if sys.platform == 'win32':
    from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, copy_metadata
    for pkg in ['paddle', 'paddleocr', 'paddlex']:
        pkg_binaries, pkg_datas = _collect_required_assets(pkg, collect_dynamic_libs, collect_data_files, copy_metadata)
        extra_binaries += pkg_binaries
        extra_datas += pkg_datas

a = Analysis(
    ['frame_extractor_gui.py'],
    pathex=[],
    binaries=extra_binaries,
    datas=[('icon.ico', '.')] + extra_datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['runtime_hook_cv2.py'],
    excludes=[
        'matplotlib',
        'tkinter',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='帧提取工具',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # 不显示控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico',  # 图标文件
)
