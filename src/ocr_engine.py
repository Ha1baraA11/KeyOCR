#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""OCR 引擎抽象层：RapidOCR (CPU) / PaddleOCR (GPU)"""

import sys
import io
import json
import importlib

# PyInstaller 窗口模式下 sys.stdout/sys.stderr 为 None
if sys.stdout is None:
    sys.stdout = io.StringIO()
if sys.stderr is None:
    sys.stderr = io.StringIO()

# Windows 下预导入 paddle + paddleocr，让 PaddleX 在主线程只初始化一次
_PADDLE_READY = False
if sys.platform == 'win32':
    try:
        import paddle  # noqa: F401
        import paddleocr  # noqa: F401
        _PADDLE_READY = True
    except Exception:
        try:
            import paddleocr  # noqa: F401
            import paddle  # noqa: F401
            _PADDLE_READY = True
        except Exception as e:
            print(f"[启动] paddle/paddleocr 预导入失败: {e}", file=sys.stderr)


def _is_paddlex_dep_error(exc):
    """检测异常是否为 paddlex 依赖缺失"""
    if "DependencyError" in type(exc).__name__ or "requires additional dependencies" in str(exc):
        return True
    cause = getattr(exc, '__cause__', None) or getattr(exc, '__context__', None)
    if cause and ("DependencyError" in type(cause).__name__ or "requires additional dependencies" in str(cause)):
        return True
    return False


def _format_exception_chain(exc):
    parts = []
    seen = set()
    current = exc
    while current and id(current) not in seen:
        seen.add(id(current))
        parts.append(f"{type(current).__name__}: {current}")
        current = getattr(current, '__cause__', None) or getattr(current, '__context__', None)
    return " <- ".join(parts)


def _can_use_paddle_gpu():
    try:
        import paddle
        return bool(paddle.device.is_compiled_with_cuda())
    except Exception:
        return False


def _write_self_check_report(output_path, report):
    if not output_path:
        return
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


class _PaddleXDepsPatch:
    """临时绕过 PaddleX 在 frozen 环境里的依赖元数据检查。"""

    def __init__(self):
        self._deps = None
        self._orig_require_extra = None
        self._orig_require_deps = None
        self._orig_is_dep_available = None
        self._cv2 = None

    def __enter__(self):
        try:
            import builtins
            import cv2
            import pyclipper
            self._cv2 = cv2
            builtins.cv2 = cv2
            builtins.pyclipper = pyclipper
            from paddlex.utils import deps as _paddlex_deps
            self._deps = _paddlex_deps
            self._orig_require_extra = getattr(_paddlex_deps, 'require_extra', None)
            self._orig_require_deps = getattr(_paddlex_deps, 'require_deps', None)
            self._orig_is_dep_available = getattr(_paddlex_deps, 'is_dep_available', None)
            if self._orig_require_extra:
                _paddlex_deps.require_extra = lambda *a, **kw: None
            if self._orig_require_deps:
                _paddlex_deps.require_deps = lambda *a, **kw: None
            if self._orig_is_dep_available:
                def _patched_is_dep_available(dep_name, *a, **kw):
                    if dep_name in ('opencv-contrib-python', 'opencv-python', 'pyclipper'):
                        return True
                    return self._orig_is_dep_available(dep_name, *a, **kw)
                _paddlex_deps.is_dep_available = _patched_is_dep_available
            try:
                import paddlex.inference.common.reader.image_reader as _image_reader
                _image_reader.cv2 = cv2
            except Exception:
                pass
            try:
                import paddlex.inference.models.text_detection.processors as _td_processors
                _td_processors.pyclipper = pyclipper
            except Exception:
                pass
        except Exception:
            pass
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            if self._deps is not None:
                if self._orig_require_extra:
                    self._deps.require_extra = self._orig_require_extra
                if self._orig_require_deps:
                    self._deps.require_deps = self._orig_require_deps
                if self._orig_is_dep_available:
                    self._deps.is_dep_available = self._orig_is_dep_available
        except Exception:
            pass


def _import_status(module_names):
    if isinstance(module_names, str):
        module_names = [module_names]
    last_error = None
    for module_name in module_names:
        try:
            module = importlib.import_module(module_name)
            return {
                "ok": True,
                "module": module_name,
                "version": getattr(module, "__version__", ""),
            }
        except Exception as e:
            last_error = e
    return {
        "ok": False,
        "module": module_names[0],
        "error": _format_exception_chain(last_error) if last_error else "unknown error",
    }


def _normalize_text_items(items):
    out = []
    if items is None:
        return out
    for item in items:
        if item is None:
            continue
        if isinstance(item, str):
            text = item.strip()
            if text:
                out.append(text)
            continue
        if isinstance(item, (list, tuple)):
            out.extend(_normalize_text_items(item))
            continue
        text = str(item).strip()
        if text:
            out.append(text)
    return out


def _normalize_score_items(items):
    out = []
    if items is None:
        return out
    for item in items:
        if item is None:
            continue
        if isinstance(item, (list, tuple)):
            out.extend(_normalize_score_items(item))
            continue
        try:
            out.append(float(item))
        except Exception:
            pass
    return out


def run_self_check(output_path=None):
    report = {
        "platform": sys.platform,
        "python": sys.version.split()[0],
        "frozen": bool(getattr(sys, "frozen", False)),
        "modules": {
            "cv2": _import_status("cv2"),
            "numpy": _import_status("numpy"),
            "rapidocr": _import_status(["rapidocr", "rapidocr_onnxruntime"]),
            "paddle": _import_status("paddle"),
            "paddleocr": _import_status("paddleocr"),
            "paddlex": _import_status("paddlex"),
        },
    }

    try:
        import paddle
        report["paddle_cuda"] = bool(paddle.device.is_compiled_with_cuda())
    except Exception as e:
        report["paddle_cuda_error"] = _format_exception_chain(e)

    try:
        _rapid = RapidOCREngine()
        report["rapidocr_engine"] = {
            "ok": True,
            "name": _rapid.name,
        }
    except Exception as e:
        report["rapidocr_engine"] = {
            "ok": False,
            "error": _format_exception_chain(e),
        }

    ok = (
        report["modules"]["cv2"]["ok"]
        and report["modules"]["rapidocr"]["ok"]
        and report.get("rapidocr_engine", {}).get("ok", False)
    )
    if sys.platform == "win32":
        ok = (
            ok
            and report["modules"]["paddle"]["ok"]
            and report["modules"]["paddleocr"]["ok"]
            and report["modules"]["paddlex"]["ok"]
            and bool(report.get("paddle_cuda"))
        )

    report["ok"] = ok
    _write_self_check_report(output_path, report)
    return 0 if ok else 1


class OCREngine:
    """OCR 引擎：自动根据平台选择 RapidOCR (Mac) 或 PaddleOCR+GPU (Windows)"""

    @staticmethod
    def create(engine_type="auto"):
        if engine_type == "auto":
            if sys.platform == "win32":
                try:
                    return PaddleOCREngine(require_gpu=True)
                except Exception as e:
                    fallback = RapidOCREngine()
                    fallback.notice = (
                        "PaddleOCR 初始化失败，已自动切换到 RapidOCR (CPU)。\n"
                        f"原因: {_format_exception_chain(e)}"
                    )
                    return fallback
            return RapidOCREngine()

        if engine_type == "gpu":
            try:
                return PaddleOCREngine(require_gpu=True)
            except Exception as e:
                fallback = RapidOCREngine()
                fallback.notice = (
                    "你当前选择的是 GPU (PaddleOCR)，但当前安装包里的 Paddle GPU 运行时不可用，"
                    "已自动切换到 RapidOCR (CPU)。\n"
                    f"原因: {_format_exception_chain(e)}"
                )
                return fallback
        return RapidOCREngine()


class RapidOCREngine:
    def __init__(self):
        try:
            from rapidocr import RapidOCR
        except ModuleNotFoundError:
            from rapidocr_onnxruntime import RapidOCR
        self._engine = RapidOCR()
        self.name = "RapidOCR (CPU)"
        self.notice = ""

    def ocr(self, img_input):
        result = self._engine(img_input)
        if result and hasattr(result, 'txts') and result.txts:
            return _normalize_text_items(result.txts), _normalize_score_items(result.scores)
        if isinstance(result, tuple):
            if len(result) >= 3:
                txts = _normalize_text_items(result[1] or [])
                scores = _normalize_score_items(result[2] or [])
                return txts, scores
            if len(result) >= 2:
                txts = _normalize_text_items(result[0] or [])
                scores = _normalize_score_items(result[1] or [])
                return txts, scores
        return [], []


class PaddleOCREngine:
    _instance = None
    _engine = None

    def __new__(cls, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, require_gpu=False):
        if self._engine is not None:
            if require_gpu and self.name != "PaddleOCR (GPU)":
                raise RuntimeError("当前环境未检测到可用 CUDA，请安装 paddlepaddle-gpu==3.3.0 并确认 NVIDIA 驱动/CUDA 11.8 可用")
            return
        try:
            import paddle
        except ModuleNotFoundError as e:
            raise RuntimeError(
                "未找到 paddle 模块，当前安装包缺少 PaddlePaddle 运行时。"
                "请在设置里改用'自动选择'或'CPU (RapidOCR)'，或重新下载最新 release。"
            ) from e
        try:
            import paddleocr
        except ModuleNotFoundError as e:
            raise RuntimeError(
                "未找到 paddleocr 模块，当前安装包缺少 PaddleOCR 运行时。"
                "请在设置里改用'自动选择'或'CPU (RapidOCR)'，或重新下载最新 release。"
            ) from e
        if not _PADDLE_READY:
            raise RuntimeError("paddle/paddleocr 预导入失败，无法初始化 GPU OCR")
        use_gpu = paddle.device.is_compiled_with_cuda()
        if require_gpu and not use_gpu:
            raise RuntimeError("当前环境未检测到可用 CUDA，请安装 paddlepaddle-gpu==3.3.0 并确认 NVIDIA 驱动/CUDA 11.8 可用")

        try:
            with _PaddleXDepsPatch():
                self._engine = paddleocr.PaddleOCR(lang='ch', use_textline_orientation=True)
        except Exception as e:
            PaddleOCREngine._instance = None
            if _is_paddlex_dep_error(e):
                raise RuntimeError(
                    "paddlex[ocr] 依赖不全，请运行: pip install \"paddlex[ocr]\""
                ) from e
            raise
        self.name = "PaddleOCR (GPU)" if use_gpu else "PaddleOCR (CPU)"

    def ocr(self, img_input):
        texts, scores = [], []
        try:
            with _PaddleXDepsPatch():
                result = self._engine.predict(img_input)
            for res in result:
                if hasattr(res, 'get'):
                    rec_texts = _normalize_text_items(res.get('rec_texts', []))
                    rec_scores = _normalize_score_items(res.get('rec_scores', []))
                    texts.extend(rec_texts)
                    scores.extend(rec_scores)
                elif hasattr(res, 'rec_texts'):
                    texts.extend(_normalize_text_items(res.rec_texts))
                    scores.extend(_normalize_score_items(res.rec_scores))
        except (AttributeError, TypeError):
            try:
                result = self._engine.ocr(img_input)
                if result and result[0]:
                    for line in result[0]:
                        try:
                            box, (text, score) = line
                            texts.append(text)
                            scores.append(score)
                        except (ValueError, TypeError):
                            pass
            except Exception as e:
                print(f"[OCR 2.x fallback error] {e}", file=sys.stderr)
        return texts, scores
