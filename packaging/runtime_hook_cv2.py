import sys
try:
    import builtins
    import cv2
    # 某些第三方模块在 frozen 环境里会直接引用全局名 cv2，
    # 但它们自己的条件导入可能因为 PyInstaller 元数据差异而没执行到。
    # 提前注入到 builtins，避免运行时 NameError: cv2 is not defined。
    builtins.cv2 = cv2
except ImportError:
    pass
