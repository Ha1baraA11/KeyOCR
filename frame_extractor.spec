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

# Windows 特有依赖：自动收集 paddle/paddleocr/paddlex 全部子模块
if sys.platform == 'win32':
    from PyInstaller.utils.hooks import collect_submodules

    # 自动发现所有子模块，比手动列举可靠
    for pkg in ['paddle', 'paddleocr', 'paddlex']:
        try:
            hidden_imports.extend(collect_submodules(pkg))
        except Exception:
            pass

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
        try:
            extra_binaries += collect_dynamic_libs(pkg)
            extra_datas += collect_data_files(pkg, include_py_files=False)
        except Exception:
            pass
    # 包含 paddlex/paddleocr 的包元数据，paddlex.utils.deps.require_extra 依赖它
    for pkg in ['paddlex', 'paddleocr', 'paddle']:
        try:
            extra_datas += copy_metadata(pkg)
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
