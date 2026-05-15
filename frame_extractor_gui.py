#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""KeyOCR 入口文件"""

import sys
import os
import io

# PyInstaller 窗口模式下 sys.stdout/sys.stderr 为 None
if sys.stdout is None:
    sys.stdout = io.StringIO()
if sys.stderr is None:
    sys.stderr = io.StringIO()

from src.ocr_engine import run_self_check, _write_self_check_report
from src.gui import FrameExtractorGUI
from src.dialogs import get_app_dir

if __name__ == "__main__":
    if os.environ.get("KEYOCR_SELF_CHECK") == "1":
        _output = os.environ.get("KEYOCR_SELF_CHECK_OUTPUT")
        try:
            sys.exit(run_self_check(_output))
        except Exception as _e:
            import traceback as _tb
            _write_self_check_report(_output, {"ok": False, "crash": _tb.format_exc()})
            sys.exit(1)
    try:
        from PySide6.QtWidgets import QApplication
        app = QApplication(sys.argv)
        window = FrameExtractorGUI()
        window.show()
        app.exec()
    except Exception as _e:
        import traceback as _tb
        _log_path = os.path.join(get_app_dir(), 'crash.log')
        try:
            with open(_log_path, 'w', encoding='utf-8') as _f:
                _f.write(_tb.format_exc())
        except Exception:
            pass
        sys.exit(1)
