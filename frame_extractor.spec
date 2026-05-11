# -*- mode: python ; coding: utf-8 -*-
import sys
import os

block_cipher = None

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

# Windows 特有依赖
if sys.platform == 'win32':
    hidden_imports.extend([
        # --- PaddlePaddle core ---
        'paddle',
        'paddle.base',
        'paddle.base.core',
        'paddle.fluid',
        'paddle.fluid.core',
        'paddle.framework',
        'paddle.device',
        'paddle.io',
        'paddle.nn',
        'paddle.inference',
        'paddle.static',
        'paddle.amp',
        'paddle._C_ops',
        'paddle.version',
        'paddle.utils',
        'paddle.utils.image_util',

        # --- PaddleOCR + PaddleX (3.x 依赖 paddlex) ---
        'paddleocr',
        'paddlex',
        'paddlex.inference',
        'paddlex.inference.models',
        'paddlex.inference.models.utils',
        'paddlex.inference.models.utils.model_config',
        'paddlex.inference.utils',
        'paddlex.inference.utils.official_models',
        'paddlex.inference.utils.io',
        'paddlex.inference.utils.io.readers',

        # --- pandas (paddlex.readers 依赖) ---
        'pandas',

        # --- PaddleOCR runtime deps ---
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

        # --- Protobuf (PaddlePaddle 内部依赖) ---
        'google.protobuf',
        'google.protobuf.descriptor',
        'google.protobuf.internal',
        'google.protobuf.message',

        # --- PIL ---
        'PIL',
        'PIL.Image',
    ])
else:
    hidden_imports.extend([
        'rapidocr',
        'rapidocr_onnxruntime',
    ])

# 收集 paddle 原生二进制文件 (.dll/.pyd)
extra_binaries = []
extra_datas = []
if sys.platform == 'win32':
    try:
        from PyInstaller.utils.hooks import collect_data_files, collect_binaries
        extra_binaries = collect_binaries('paddle')
        extra_datas = collect_data_files('paddle', include_py_files=False)
    except Exception:
        pass

a = Analysis(
    ['frame_extractor_gui.py'],
    pathex=[],
    binaries=extra_binaries,
    datas=[('icon.ico', '.')] + extra_datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
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
