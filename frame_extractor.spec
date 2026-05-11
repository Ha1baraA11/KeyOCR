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
        'paddle',
        'paddleocr',
        'paddle.fluid',
        'paddle.fluid.core',
        'paddle.utils',
        'paddle.utils.image_util',
        'PIL',
        'PIL.Image',
    ])
else:
    hidden_imports.extend([
        'rapidocr',
        'rapidocr_onnxruntime',
    ])

a = Analysis(
    ['frame_extractor_gui.py'],
    pathex=[],
    binaries=[],
    datas=[('icon.ico', '.')],
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'scipy',
        'pandas',
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
