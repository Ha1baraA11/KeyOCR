#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
视频分帧工具 - GUI
从视频中按指定间隔截取帧并保存为图片
"""

import sys
import os
import io
import importlib

# PyInstaller 窗口模式下 sys.stdout/sys.stderr 为 None，
# PaddleX 下载模型时 print() 会 AttributeError。提前补上空流。
if sys.stdout is None:
    sys.stdout = io.StringIO()
if sys.stderr is None:
    sys.stderr = io.StringIO()

import json
import tempfile
import shutil
import platform
import time
import cv2
import numpy as np
from pathlib import Path
from PySide6.QtCore import Qt, QThread, Signal, QPoint, QRect, QUrl
from PySide6.QtGui import QFont, QPixmap, QImage, QPainter, QPen, QColor, QCursor, QDesktopServices
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QSpinBox, QDoubleSpinBox, QFileDialog,
    QProgressBar, QTextEdit, QGroupBox, QDialog, QDialogButtonBox, QLineEdit,
    QMessageBox, QComboBox, QCheckBox
)

# Windows 下预导入 paddle + paddleocr，让 PaddleX 在主线程只初始化一次
# 仅做 import（不创建实例），PaddleX 的 import-time 初始化在主线程完成
# PaddleOCR() 实例化在 PaddleOCREngine 中延迟执行
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
            # 注意：预导入只做 import，不会触发 DependencyError（那是 PaddleOCR() 创建时的错误）
            print(f"[启动] paddle/paddleocr 预导入失败: {e}", file=sys.stderr)


# --- OCR 引擎抽象层 ---

def _is_paddlex_dep_error(exc):
    """检测异常是否为 paddlex 依赖缺失（DependencyError 可能是外层，也可能是 __cause__）"""
    # 检查外层异常
    if "DependencyError" in type(exc).__name__ or "requires additional dependencies" in str(exc):
        return True
    # 检查内层 cause（PaddleOCR 把 DependencyError 包装成 RuntimeError）
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


def _write_self_check_report(output_path, report):
    if not output_path:
        return
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
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

    ok = report["modules"]["cv2"]["ok"] and report["modules"]["rapidocr"]["ok"]
    if sys.platform == "win32":
        ok = ok and report["modules"]["paddle"]["ok"] and report["modules"]["paddleocr"]["ok"] and report["modules"]["paddlex"]["ok"]

    report["ok"] = ok
    _write_self_check_report(output_path, report)
    return 0 if ok else 1

class OCREngine:
    """OCR 引擎：自动根据平台选择 RapidOCR (Mac) 或 PaddleOCR+GPU (Windows)"""

    @staticmethod
    def create(engine_type="auto"):
        """
        engine_type: "auto" | "cpu" | "gpu"
        auto: Mac 用 RapidOCR, Windows 用 PaddleOCR
        cpu: 强制用 RapidOCR
        gpu: 强制用 PaddleOCR
        """
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
            return PaddleOCREngine(require_gpu=True)
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
        """img_input: 图片路径(str) 或 numpy 数组
        返回: (texts: list[str], scores: list[float])"""
        result = self._engine(img_input)
        if result and result.txts:
            return list(result.txts), list(result.scores)
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
                "请在设置里改用“自动选择”或“CPU (RapidOCR)”，或重新下载最新 release。"
            ) from e
        try:
            import paddleocr
        except ModuleNotFoundError as e:
            raise RuntimeError(
                "未找到 paddleocr 模块，当前安装包缺少 PaddleOCR 运行时。"
                "请在设置里改用“自动选择”或“CPU (RapidOCR)”，或重新下载最新 release。"
            ) from e
        if not _PADDLE_READY:
            raise RuntimeError("paddle/paddleocr 预导入失败，无法初始化 GPU OCR")
        use_gpu = paddle.device.is_compiled_with_cuda()
        if require_gpu and not use_gpu:
            raise RuntimeError("当前环境未检测到可用 CUDA，请安装 paddlepaddle-gpu==3.3.0 并确认 NVIDIA 驱动/CUDA 11.8 可用")

        # PaddleX 的 require_extra/require_deps/is_dep_available 通过 importlib.metadata 检查包名，
        # 但 PyInstaller 打包后元数据丢失，且 opencv-contrib-python 与 opencv-python
        # 的包名冲突也会导致误报。既然依赖已确认安装（import 成功），直接跳过检查。
        # 特别是 is_dep_available("opencv-contrib-python") 返回 False 会导致
        # image_reader.py 不执行 import cv2，后续使用 cv2 时 NameError。
        import cv2  # noqa: F401
        _orig_require_extra = None
        _orig_require_deps = None
        _orig_is_dep_available = None
        try:
            from paddlex.utils import deps as _paddlex_deps
            _orig_require_extra = getattr(_paddlex_deps, 'require_extra', None)
            _orig_require_deps = getattr(_paddlex_deps, 'require_deps', None)
            if _orig_require_extra:
                _paddlex_deps.require_extra = lambda *a, **kw: None
            if _orig_require_deps:
                _paddlex_deps.require_deps = lambda *a, **kw: None
            # patch is_dep_available，让 image_reader.py 的条件导入生效
            _orig_is_dep_available = getattr(_paddlex_deps, 'is_dep_available', None)
            if _orig_is_dep_available:
                def _patched_is_dep_available(dep_name, *a, **kw):
                    if dep_name in ('opencv-contrib-python', 'opencv-python'):
                        return True
                    return _orig_is_dep_available(dep_name, *a, **kw)
                _paddlex_deps.is_dep_available = _patched_is_dep_available
        except Exception:
            pass

        try:
            # PaddleOCR 3.x API: use_angle_cls → use_textline_orientation,
            # show_log/use_gpu 已移除
            self._engine = paddleocr.PaddleOCR(lang='ch', use_textline_orientation=True)
        except Exception as e:
            PaddleOCREngine._instance = None
            if _is_paddlex_dep_error(e):
                raise RuntimeError(
                    "paddlex[ocr] 依赖不全，请运行: pip install \"paddlex[ocr]\""
                ) from e
            raise
        finally:
            # 恢复原始函数
            try:
                if _orig_require_extra:
                    _paddlex_deps.require_extra = _orig_require_extra
                if _orig_require_deps:
                    _paddlex_deps.require_deps = _orig_require_deps
                if _orig_is_dep_available:
                    _paddlex_deps.is_dep_available = _orig_is_dep_available
            except Exception:
                pass
        self.name = "PaddleOCR (GPU)" if use_gpu else "PaddleOCR (CPU)"

    def ocr(self, img_input):
        """img_input: 图片路径(str) 或 numpy 数组
        返回: (texts: list[str], scores: list[float])"""
        texts, scores = [], []
        try:
            # PaddleOCR 3.x: predict() 返回 OCRResult 字典列表
            result = self._engine.predict(img_input)
            for res in result:
                if hasattr(res, 'get'):
                    rec_texts = res.get('rec_texts', [])
                    rec_scores = res.get('rec_scores', [])
                    texts.extend(rec_texts)
                    scores.extend(rec_scores)
                elif hasattr(res, 'rec_texts'):
                    texts.extend(res.rec_texts)
                    scores.extend(res.rec_scores)
        except (AttributeError, TypeError):
            # PaddleOCR 2.x 兼容: ocr() 返回 [(box, (text, score)), ...]
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


# --- 筛选算法（模块级函数，供 SmartExtractWorker 复用）---

def _get_candidates(diffs, prev_max, next_min, ratio_min, ratio_max, spike_mult=0):
    """筛选候选帧: 满足 prev_diff <= prev_max, next_diff >= next_min, ratio 在范围内"""
    candidates = []
    for i in range(2, len(diffs) - 1):
        if diffs[i] <= 0 or diffs[i - 1] <= 0:
            continue
        r = diffs[i + 1] / diffs[i] if diffs[i] > 0 else 0
        if (diffs[i - 1] <= prev_max and diffs[i] <= prev_max
                and diffs[i + 1] >= next_min and ratio_min <= r <= ratio_max):
            if spike_mult > 0:
                start = max(1, i - 5)
                end = min(len(diffs), i + 6)
                context_median = np.median(diffs[start:end])
                if context_median > 0 and diffs[i + 1] > context_median * spike_mult:
                    continue
            score = r * diffs[i + 1]
            candidates.append((i, score))
    return candidates


def _greedy_select(candidates, gap, selected=None):
    """贪心选择: 按 score 从高到低，满足 gap 约束就选中"""
    if selected is None:
        selected = []
    for idx, score in sorted(candidates, key=lambda x: x[1], reverse=True):
        if all(abs(idx - s) >= gap for s in selected):
            selected.append(idx)
    return selected


def _twopass_select(diffs, files, log_fn=None):
    """两遍选择: 第一遍严格高置信, 第二遍宽松补充
    prev/next 阈值自适应，gap 根据帧数缩放"""
    nonzero = diffs[diffs > 0]
    if len(nonzero) == 0:
        return []

    median_diff = np.median(nonzero)
    n = len(files)

    # prev_max: 宽松（ratio 是主筛选器）
    # next_min: 基于中位数自适应
    pm = np.percentile(nonzero, 85)
    nm1 = median_diff * 1.25
    nm2 = median_diff * 1.0

    # gap: 基于帧数线性缩放
    gap1 = max(15, int(n * 0.014))
    gap2 = max(20, int(n * 0.017))

    if log_fn:
        log_fn(f"diff 统计: median={median_diff:.1f}, 帧数={n}")
        log_fn(f"自适应: prev<={pm:.1f}, 第一遍 next>={nm1:.1f} gap={gap1}")
        log_fn(f"         第二遍 next>={nm2:.1f} gap={gap2}")

    c1 = _get_candidates(diffs, prev_max=pm, next_min=nm1,
                         ratio_min=1.5, ratio_max=3.5, spike_mult=3.0)
    sel = _greedy_select(c1, gap=gap1)
    if log_fn:
        log_fn(f"第一遍: {len(c1)} 候选, 选中 {len(sel)} 帧")

    c2 = _get_candidates(diffs, prev_max=pm, next_min=nm2,
                         ratio_min=1.2, ratio_max=5.0, spike_mult=0)
    sel = _greedy_select(c2, gap=gap2, selected=list(sel))
    if log_fn:
        log_fn(f"第二遍: {len(c2)} 候选, 累计选中 {len(sel)} 帧")

    if files and sel and len(files) - 1 - sel[-1] >= gap2:
        sel.append(len(files) - 1)
    sel.sort()
    return sel


def _find_transition_peaks(diffs, thresh_mult=1.5, min_dist_frames=7):
    """检测转换峰值: next_diff 超过中位数 × thresh_mult 的局部最大值
    min_dist_frames: 峰值合并距离(帧索引单位)"""
    nonzero = diffs[diffs > 0]
    if len(nonzero) == 0:
        return []
    threshold = np.median(nonzero) * thresh_mult
    peaks = []
    for i in range(2, len(diffs) - 1):
        if diffs[i + 1] > threshold:
            if diffs[i + 1] >= diffs[i] and (i + 2 >= len(diffs) or diffs[i + 1] >= diffs[i + 2]):
                peaks.append(i)
    if not peaks:
        return peaks
    merged = [peaks[0]]
    for p in peaks[1:]:
        if p - merged[-1] >= min_dist_frames:
            merged.append(p)
        elif diffs[p + 1] > diffs[merged[-1] + 1]:
            merged[-1] = p
    return merged


def _read_frame(path, flags=cv2.IMREAD_COLOR):
    """读取帧图片，Windows 中文路径兼容"""
    img = cv2.imread(path, flags)
    if img is not None:
        return img
    try:
        with open(path, 'rb') as f:
            buf = np.frombuffer(f.read(), dtype=np.uint8)
        return cv2.imdecode(buf, flags)
    except Exception:
        return None


def _safe_open_path(path):
    """Windows 中文路径兼容：创建临时符号链接到纯英文路径，返回安全路径。
    非 Windows 或纯 ASCII 路径直接返回原路径。"""
    if sys.platform != 'win32' or path.isascii():
        return path, None
    import ctypes
    tmp_dir = tempfile.mkdtemp(prefix="zt_")
    ext = os.path.splitext(path)[1]
    safe_link = os.path.join(tmp_dir, "file" + ext)
    try:
        os.symlink(path, safe_link)
        return safe_link, tmp_dir
    except OSError:
        # symlink 需要权限，回退：用 8.3 短路径
        try:
            buf = ctypes.create_unicode_buffer(512)
            if ctypes.windll.kernel32.GetShortPathNameW(path, buf, 512):
                return buf.value, None
        except Exception:
            pass
        print(f"[WARNING] 中文路径兼容失败（symlink 和 8.3 短路径均不可用）: {path}", file=sys.stderr)
        return path, None


def _cleanup_safe_path(tmp_dir):
    """清理 _safe_open_path 创建的临时目录"""
    if tmp_dir:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass


def _compute_diffs(frames_dir, files):
    """计算一组帧文件的相邻帧差异，返回 diffs 数组"""
    diffs = []
    prev_img = None
    for fname in files:
        img = _read_frame(os.path.join(frames_dir, fname), cv2.IMREAD_GRAYSCALE)
        if img is None:
            diffs.append(0)
            continue
        if prev_img is not None:
            if prev_img.shape != img.shape:
                img = cv2.resize(img, (prev_img.shape[1], prev_img.shape[0]))
            diff = np.mean(np.abs(prev_img.astype(float) - img.astype(float)))
            diffs.append(diff)
        else:
            diffs.append(0)
        prev_img = img
    return np.array(diffs)


def _extract_frame_number(filename):
    """从 frame_XXXXXX.png 提取帧号"""
    try:
        return int(filename.replace("frame_", "").replace(".png", ""))
    except ValueError:
        return 0


class FilterWorker(QThread):
    """智能筛选：从截取的帧中找出完整页面"""
    progress = Signal(int, int)
    log = Signal(str)
    finished = Signal(bool, str)

    def __init__(self, frames_dir):
        super().__init__()
        self.frames_dir = frames_dir
        self._running = True

    def run(self):
        try:
            files = sorted([
                f for f in os.listdir(self.frames_dir)
                if f.startswith("frame_") and f.endswith(".png")
            ])
            if len(files) < 2:
                self.finished.emit(False, "帧数不足，无法筛选")
                return

            self.log.emit(f"共 {len(files)} 帧待分析")

            diffs = _compute_diffs(self.frames_dir, files)
            if len(diffs) < 3:
                self.finished.emit(False, "帧数不足，无法筛选")
                return

            self.progress.emit(len(files), len(files))

            diff_min = np.min(diffs[diffs > 0]) if np.any(diffs > 0) else 0
            diff_median = np.median(diffs[diffs > 0]) if np.any(diffs > 0) else 0
            self.log.emit(f"差异范围: {diff_min:.1f} ~ {np.max(diffs):.1f}, 中位数: {diff_median:.1f}")

            selected_indices = _twopass_select(diffs, files, log_fn=self.log.emit)

            if not selected_indices:
                self.log.emit("未找到完整页面")
                self.finished.emit(False, "未找到完整页面")
                return

            selected_indices = sorted(set(selected_indices))
            selected_dir = os.path.join(self.frames_dir, "selected")
            os.makedirs(selected_dir, exist_ok=True)

            self.log.emit(f"---\n找到 {len(selected_indices)} 个完整页面:")
            for idx in selected_indices:
                src = os.path.join(self.frames_dir, files[idx])
                dst = os.path.join(selected_dir, files[idx])
                shutil.copy2(src, dst)
                self.log.emit(f"  ✓ {files[idx]}")

            self.log.emit(f"---")
            self.log.emit(f"筛选完成! 共 {len(selected_indices)} 张完整页面")
            self.log.emit(f"把你的 OCR 工具指向这个目录:")
            self.log.emit(f"  → {selected_dir}")
            self.finished.emit(True, f"筛选完成，共 {len(selected_indices)} 张完整页面")

        except Exception as e:
            self.finished.emit(False, f"错误: {e}")

    def stop(self):
        self._running = False


class SmartExtractWorker(QThread):
    """粗扫+转换点检测：低帧率截帧，检测页面转换峰值，提取峰值前的帧"""
    progress = Signal(int, int)
    log = Signal(str)
    finished = Signal(bool, str)
    coarse_ready = Signal(str)  # 粗扫完成，发送粗扫帧目录

    def __init__(self, video_path, output_dir, coarse_fps, margin_sec):
        super().__init__()
        self.video_path = video_path
        self.output_dir = output_dir
        self.coarse_fps = coarse_fps
        self.margin_sec = margin_sec
        self._running = True
        self._safe_video, self._safe_tmp = _safe_open_path(video_path)

    def _open_video(self):
        cap = cv2.VideoCapture(self._safe_video)
        return cap

    def run(self):
        try:
            cap = self._open_video()
            if not cap.isOpened():
                self.finished.emit(False, "无法打开视频文件")
                return

            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            video_fps = cap.get(cv2.CAP_PROP_FPS)
            duration_sec = total_frames / video_fps if video_fps > 0 else 0

            self.log.emit(f"视频信息: {total_frames} 帧, {video_fps:.1f} fps, {duration_sec:.1f} 秒")
            self.log.emit(f"扫描帧率: {self.coarse_fps} fps | 每个峰值只取1帧")
            cap.release()

            # === 阶段1: 粗扫截帧 ===
            self.log.emit(f"\n{'='*40}")
            self.log.emit(f"阶段1: 粗扫截帧 ({self.coarse_fps} fps)")
            self.log.emit(f"{'='*40}")

            coarse_dir = os.path.join(self.output_dir, "coarse")
            if os.path.exists(coarse_dir):
                shutil.rmtree(coarse_dir)
            os.makedirs(coarse_dir)

            coarse_interval = max(1, int(video_fps / self.coarse_fps))
            coarse_count = self._extract_frames(coarse_dir, coarse_interval, total_frames, video_fps)
            if coarse_count == 0:
                self.finished.emit(False, "截帧失败")
                return

            self.log.emit(f"截帧完成: {coarse_count} 帧")

            # 通知 GUI 粗扫完成，可以开始选区域
            coarse_files = sorted([f for f in os.listdir(coarse_dir)
                                   if f.startswith("frame_") and f.endswith(".png")])
            if not coarse_files:
                self.finished.emit(False, "截帧文件写入失败，请检查路径是否含中文或特殊字符")
                return
            self.coarse_ready.emit(coarse_dir)

            # === 阶段2: 检测转换峰值 ===
            self.log.emit(f"\n{'='*40}")
            self.log.emit(f"阶段2: 检测转换峰值")
            self.log.emit(f"{'='*40}")
            coarse_diffs = _compute_diffs(coarse_dir, coarse_files)

            if len(coarse_diffs) < 3:
                self.finished.emit(False, "帧数不足")
                return

            nonzero = coarse_diffs[coarse_diffs > 0]
            median_diff = np.median(nonzero)
            min_dist_frames = 5  # 优化: 从7改为5，覆盖率100%
            peaks = _find_transition_peaks(coarse_diffs, thresh_mult=1.5,
                                           min_dist_frames=min_dist_frames)

            self.log.emit(f"diff 中位数: {median_diff:.1f}")
            self.log.emit(f"检测阈值: > {median_diff * 1.5:.1f} (1.5x 中位数)")
            self.log.emit(f"最小间距: {min_dist_frames} 帧")
            self.log.emit(f"检测到 {len(peaks)} 个转换峰值")

            if not peaks:
                self.log.emit("未检测到转换峰值")
                self.finished.emit(False, "未检测到转换峰值")
                return

            for i, pidx in enumerate(peaks[:10]):
                pframe = _extract_frame_number(coarse_files[pidx])
                self.log.emit(f"  峰点 {i}: frame {pframe} @ {pframe/video_fps:.1f}s "
                              f"(next_diff={coarse_diffs[pidx+1]:.1f})")
            if len(peaks) > 10:
                self.log.emit(f"  ... (共 {len(peaks)} 个)")

            # === 阶段3: 提取峰值后的第一个稳定帧 ===
            self.log.emit(f"\n{'='*40}")
            self.log.emit(f"阶段3: 提取峰值后的稳定帧")
            self.log.emit(f"{'='*40}")

            selected_dir = os.path.join(self.output_dir, "selected")
            if os.path.exists(selected_dir):
                shutil.rmtree(selected_dir)
            os.makedirs(selected_dir)

            # 直接取峰值处的帧
            stable_frames = []
            for pidx in peaks:
                peak_frame = _extract_frame_number(coarse_files[pidx])
                stable_frames.append(peak_frame)

            self.log.emit(f"找到 {len(stable_frames)} 个稳定帧")

            saved_frames = set()
            cap = self._open_video()
            for frame_no in stable_frames:
                if frame_no not in saved_frames:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_no)
                    ret, frame = cap.read()
                    if ret:
                        SmartExtractWorker._write_frame(os.path.join(selected_dir, f"frame_{frame_no:06d}.png"), frame)
                        saved_frames.add(frame_no)
            cap.release()

            self.log.emit(f"提取完成: {len(saved_frames)} 帧")

            # === 输出结果 ===
            selected_files = sorted([f for f in os.listdir(selected_dir)
                                     if f.startswith("frame_") and f.endswith(".png")])

            compression = len(saved_frames) / total_frames * 100 if total_frames > 0 else 0
            self.log.emit(f"\n{'='*40}")
            self.log.emit(f"结果: {len(selected_files)} 帧 (原视频 {total_frames} 帧, 压缩率 {compression:.1f}%)")
            self.log.emit(f"{'='*40}")
            self.log.emit(f"输出目录: {selected_dir}")
            self.finished.emit(True, f"完成，共 {len(selected_files)} 帧 (压缩率 {compression:.1f}%)")

        except Exception as e:
            self.finished.emit(False, f"错误: {e}")
        finally:
            _cleanup_safe_path(self._safe_tmp)

    @staticmethod
    def _write_frame(path, frame):
        """写入帧图片，Windows 中文路径兼容"""
        if cv2.imwrite(path, frame):
            return True
        # Windows 中文路径回退：用 numpy + 文件 IO
        try:
            _, buf = cv2.imencode('.png', frame)
            with open(path, 'wb') as f:
                f.write(buf.tobytes())
            return True
        except Exception:
            return False

    def _extract_frames(self, output_dir, interval, total_frames, video_fps):
        """从视频中按间隔截帧，返回保存的帧数"""
        cap = self._open_video()
        if not cap.isOpened():
            return 0

        frame_no = 0
        saved = 0
        while frame_no < total_frames and self._running:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_no)
            ret, frame = cap.read()
            if not ret:
                break
            filename = f"frame_{frame_no:06d}.png"
            if self._write_frame(os.path.join(output_dir, filename), frame):
                saved += 1
            self.progress.emit(frame_no + 1, total_frames)
            frame_no += interval

        cap.release()
        return saved

    def _extract_frames_range(self, output_dir, interval, start_frame, end_frame, video_fps, offset=0):
        """从视频的指定范围截帧"""
        cap = self._open_video()
        if not cap.isOpened():
            return 0

        frame_no = start_frame
        saved = 0
        while frame_no <= end_frame and self._running:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_no)
            ret, frame = cap.read()
            if not ret:
                break
            filename = f"frame_{frame_no:06d}.png"
            if self._write_frame(os.path.join(output_dir, filename), frame):
                saved += 1
            frame_no += interval

        cap.release()
        return saved

    def _merge_ranges(self, ranges):
        """合并重叠的时间区间"""
        if not ranges:
            return []
        sorted_ranges = sorted(ranges, key=lambda x: x[0])
        merged = [sorted_ranges[0]]
        for start, end in sorted_ranges[1:]:
            if start <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((start, end))
        return merged

    def stop(self):
        self._running = False


class RegionSelectorDialog(QDialog):
    """区域选择对话框：显示示例帧，用户拖拽选定 OCR 区域"""

    def __init__(self, image_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("选择 OCR 区域")
        self.setMinimumSize(800, 600)

        # 加载原图（兼容中文路径）
        img = _read_frame(image_path)
        if img is None:
            raise ValueError(f"无法加载图片: {image_path}")
        h, w, ch = img.shape
        bytes_per_line = ch * w
        # OpenCV 是 BGR，QImage 需要 RGB
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        qimg = QImage(img_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
        self.original_pixmap = QPixmap.fromImage(qimg.copy())

        self.orig_w = self.original_pixmap.width()
        self.orig_h = self.original_pixmap.height()

        # 选区状态（在缩放后的坐标系中）
        self._selecting = False
        self._start_pos = None
        self._rect = QRect()  # 当前选区（显示坐标）
        self.region = None  # 最终结果 (x, y, w, h) 相对比例

        # UI
        layout = QVBoxLayout(self)
        self.info_label = QLabel("在图片上拖拽选择 OCR 区域，然后点确认")
        layout.addWidget(self.info_label)

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.image_label, 1)

        btn_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btn_box.accepted.connect(self._on_accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

        self._update_display()

    def _update_display(self):
        """缩放图片到窗口大小并显示，叠加选区矩形"""
        available = self.image_label.size()
        scaled = self.original_pixmap.scaled(
            available, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self._scale_w = scaled.width()
        self._scale_h = scaled.height()

        # 在缩放图上画选区
        canvas = scaled.copy()
        if not self._rect.isNull() and self._rect.width() > 0 and self._rect.height() > 0:
            painter = QPainter(canvas)
            pen = QPen(QColor(255, 0, 0), 2, Qt.SolidLine)
            painter.setPen(pen)
            # 半透明填充
            painter.setBrush(QColor(255, 0, 0, 40))
            painter.drawRect(self._rect)
            painter.end()

        self.image_label.setPixmap(canvas)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            pos = self._to_image_pos(event.position().toPoint())
            if pos:
                self._selecting = True
                self._start_pos = pos
                self._rect = QRect(pos, pos)
                self._update_display()

    def mouseMoveEvent(self, event):
        if self._selecting:
            pos = self._to_image_pos(event.position().toPoint())
            if pos:
                self._rect = QRect(self._start_pos, pos).normalized()
                self._update_display()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._selecting:
            self._selecting = False
            pos = self._to_image_pos(event.position().toPoint())
            if pos:
                self._rect = QRect(self._start_pos, pos).normalized()
                self._update_display()

    def _to_image_pos(self, widget_pos):
        """将 widget 坐标转换为缩放图片上的坐标"""
        # 图片在 label 中居中显示，计算偏移
        label_rect = self.image_label.geometry()
        offset_x = (label_rect.width() - self._scale_w) // 2
        offset_y = (label_rect.height() - self._scale_h) // 2

        x = widget_pos.x() - self.image_label.x() - offset_x
        y = widget_pos.y() - self.image_label.y() - offset_y

        if 0 <= x < self._scale_w and 0 <= y < self._scale_h:
            return QPoint(x, y)
        return None

    def _on_accept(self):
        if self._rect.isNull() or self._rect.width() < 5 or self._rect.height() < 5:
            self.region = None
        else:
            # 转换为原图相对比例
            rx = self._rect.x() / self._scale_w
            ry = self._rect.y() / self._scale_h
            rw = self._rect.width() / self._scale_w
            rh = self._rect.height() / self._scale_h
            self.region = (rx, ry, rw, rh)
        self.accept()


class BatchOCRWorker(QThread):
    """批量 OCR：对目录中的图片逐张识别，输出合并文本"""
    progress = Signal(int, int)
    log = Signal(str)
    finished = Signal(bool, str)

    def __init__(self, input_dir, output_path, region=None, engine_type="auto"):
        super().__init__()
        self.input_dir = input_dir
        self.output_path = output_path
        self.region = region  # (x, y, w, h) 相对比例，None 表示全图
        self.engine_type = engine_type
        self._running = True

    def run(self):
        try:
            exts = {'.png', '.jpg', '.jpeg', '.bmp', '.webp'}
            files = sorted([
                f for f in os.listdir(self.input_dir)
                if Path(f).suffix.lower() in exts
            ])
            if not files:
                self.finished.emit(False, "目录中无图片文件")
                return

            self.log.emit(f"共 {len(files)} 张图片，开始 OCR...")
            if self.region:
                self.log.emit(f"OCR 区域: x={self.region[0]:.2f} y={self.region[1]:.2f} "
                              f"w={self.region[2]:.2f} h={self.region[3]:.2f}")
            engine = OCREngine.create(self.engine_type)
            if getattr(engine, "notice", ""):
                self.log.emit(engine.notice)
            self.log.emit(f"OCR 引擎: {engine.name}")

            results = []
            for i, fname in enumerate(files):
                if not self._running:
                    self.finished.emit(False, "已停止")
                    return

                fpath = os.path.join(self.input_dir, fname)
                if self.region:
                    img = _read_frame(fpath)
                    if img is None:
                        self.log.emit(f"[{i+1}/{len(files)}] {fname}: 读取失败，跳过")
                        results.append(f"=== {fname} ===\n(读取失败)")
                        self.progress.emit(i + 1, len(files))
                        continue
                    h, w = img.shape[:2]
                    rx, ry, rw, rh = self.region
                    x1, y1 = int(rx * w), int(ry * h)
                    x2, y2 = int((rx + rw) * w), int((ry + rh) * h)
                    img = img[y1:y2, x1:x2]
                    texts, scores = engine.ocr(img)
                else:
                    img = _read_frame(fpath)
                    if img is None:
                        self.log.emit(f"[{i+1}/{len(files)}] {fname}: 读取失败，跳过")
                        results.append(f"=== {fname} ===\n(读取失败)")
                        self.progress.emit(i + 1, len(files))
                        continue
                    texts, scores = engine.ocr(img)

                if texts:
                    text = "\n".join(texts)
                    avg_score = sum(scores) / len(scores)
                    results.append(f"=== {fname} (置信度 {avg_score:.2f}) ===\n{text}")
                    self.log.emit(f"[{i+1}/{len(files)}] {fname}: {len(texts)} 行文字")
                else:
                    results.append(f"=== {fname} ===\n(无文字)")
                    self.log.emit(f"[{i+1}/{len(files)}] {fname}: 无文字")

                self.progress.emit(i + 1, len(files))

            with open(self.output_path, 'w', encoding='utf-8') as f:
                f.write("\n\n".join(results) + "\n")

            self.finished.emit(True, f"完成，已保存到 {os.path.basename(self.output_path)}")

        except Exception as e:
            import traceback
            self.finished.emit(False, f"错误: {e}\n{traceback.format_exc()}")

    def stop(self):
        self._running = False


class AICleanupWorker(QThread):
    """调用 AI API 对 OCR 结果进行纠错和润色"""
    log = Signal(str)
    finished = Signal(bool, str)

    API_URL = "https://token-plan-cn.xiaomimimo.com/anthropic/v1/messages"
    API_KEY = ""
    MODEL = "mimo-v2.5-pro"

    def __init__(self, ocr_text, output_path):
        super().__init__()
        self.ocr_text = ocr_text
        self.output_path = output_path
        self._running = True

    def run(self):
        try:
            import requests

            self.log.emit("正在调用 AI 纠错润色...")

            prompt = (
                "以下是从视频帧中 OCR 识别出的文字，按帧的顺序排列。\n\n"
                "【你的任务】\n"
                "把这段文字改写成口语化的大白话文案，就像平时说话一样自然。"
                "不要用文言文、书面语、成语堆砌，要用大白话。"
                "OCR 有错字，你需要根据上下文纠正。\n\n"
                "【格式要求】\n"
                "- 最好一行就是完整的一句话\n"
                "- 一行可以是任意字数，没有上限\n"
                "- 但两行加在一起不能超过 12 个字\n"
                "- 读起来像说话，有停顿感\n\n"
                "【内容要求】\n"
                "- 涉及\"橱窗\"的内容必须保留原文意思，一个字都不能改\n"
                "- 其他内容可以自由改写，只要大意相近、能吸引人就行\n"
                "- 可以加情绪、加画面感、加悬念\n"
                "- 不要加任何编号、符号、标题、解释，只输出纯文字\n\n"
                f"OCR 原文：\n{self.ocr_text}"
            )

            headers = {
                "x-api-key": self.API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            }
            payload = {
                "model": self.MODEL,
                "max_tokens": 8192,
                "messages": [{"role": "user", "content": prompt}],
            }

            resp = requests.post(self.API_URL, headers=headers, json=payload, timeout=120)
            resp.raise_for_status()
            data = resp.json()

            # 提取 AI 回复
            ai_text = ""
            for block in data.get("content", []):
                if block.get("type") == "text":
                    ai_text += block["text"]

            if not ai_text.strip():
                self.finished.emit(False, "AI 返回为空")
                return

            # 写入最终版.txt
            with open(self.output_path, 'w', encoding='utf-8') as f:
                f.write(ai_text.strip() + "\n")

            self.log.emit(f"AI 纠错完成，已保存到 {os.path.basename(self.output_path)}")
            self.finished.emit(True, f"AI 纠错完成，已保存到 {os.path.basename(self.output_path)}")

        except Exception as e:
            self.finished.emit(False, f"AI 调用失败: {e}")

    def stop(self):
        self._running = False


class SettingsDialog(QDialog):
    """设置对话框：API 配置、环境检测、缓存管理"""

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setMinimumWidth(500)
        self.setMinimumHeight(500)
        self.settings = dict(settings)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # === API 配置 ===
        api_group = QGroupBox("API 配置")
        api_layout = QVBoxLayout(api_group)
        api_layout.addWidget(QLabel("API Key"))
        self.api_key_edit = QLineEdit(self.settings.get("api_key", ""))
        self.api_key_edit.setEchoMode(QLineEdit.Password)
        api_layout.addWidget(self.api_key_edit)
        api_layout.addWidget(QLabel("API 地址"))
        self.api_url_edit = QLineEdit(self.settings.get("api_url", ""))
        api_layout.addWidget(self.api_url_edit)
        api_layout.addWidget(QLabel("模型名称"))
        self.model_edit = QLineEdit(self.settings.get("model", ""))
        api_layout.addWidget(self.model_edit)
        # 测试按钮
        btn_test = QPushButton("测试 API 连接")
        btn_test.setFixedHeight(30)
        btn_test.clicked.connect(self._test_api)
        api_layout.addWidget(btn_test)
        self.api_status = QLabel("")
        self.api_status.setStyleSheet("color: #888;")
        api_layout.addWidget(self.api_status)
        layout.addWidget(api_group)

        # === OCR 模式 ===
        mode_group = QGroupBox("OCR 区域模式")
        mode_layout = QVBoxLayout(mode_group)
        mode_layout.addWidget(QLabel("自动模式：自动检测纯色区域 | 手动模式：手动框选区域"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("自动 OCR", "auto")
        self.mode_combo.addItem("手动 OCR", "manual")
        saved_mode = self.settings.get("ocr_mode", "auto")
        for i in range(self.mode_combo.count()):
            if self.mode_combo.itemData(i) == saved_mode:
                self.mode_combo.setCurrentIndex(i)
                break
        mode_layout.addWidget(self.mode_combo)
        layout.addWidget(mode_group)

        # === OCR 引擎 ===
        ocr_group = QGroupBox("OCR 引擎")
        ocr_layout = QVBoxLayout(ocr_group)
        self.engine_combo = QComboBox()
        self.engine_combo.addItem("自动选择", "auto")
        self.engine_combo.addItem("CPU (RapidOCR)", "cpu")
        self.engine_combo.addItem("GPU (PaddleOCR)", "gpu")
        # 恢复上次选择
        saved_engine = self.settings.get("ocr_engine", "auto")
        for i in range(self.engine_combo.count()):
            if self.engine_combo.itemData(i) == saved_engine:
                self.engine_combo.setCurrentIndex(i)
                break
        ocr_layout.addWidget(self.engine_combo)
        ocr_layout.addWidget(QLabel("自动：优先 PaddleOCR，失败时自动回退到 RapidOCR"))
        layout.addWidget(ocr_group)

        # === 环境检测 ===
        env_group = QGroupBox("环境检测")
        env_layout = QVBoxLayout(env_group)
        btn_check = QPushButton("开始检测")
        btn_check.setFixedHeight(30)
        btn_check.clicked.connect(self._check_env)
        env_layout.addWidget(btn_check)
        self.env_log = QTextEdit()
        self.env_log.setReadOnly(True)
        self.env_log.setFont(QFont("Menlo", 10))
        self.env_log.setMaximumHeight(150)
        self.env_log.setStyleSheet("QTextEdit { background-color: #1e1e1e; color: #d4d4d4; }")
        env_layout.addWidget(self.env_log)
        layout.addWidget(env_group)

        # === 缓存管理 ===
        cache_group = QGroupBox("缓存管理")
        cache_layout = QHBoxLayout(cache_group)
        cache_layout.addWidget(QLabel("手动清除中间文件（保留最终版）"), 1)
        btn_clear = QPushButton("清除缓存")
        btn_clear.setFixedHeight(30)
        btn_clear.setStyleSheet("QPushButton { color: #f44336; }")
        btn_clear.clicked.connect(self._clear_cache)
        cache_layout.addWidget(btn_clear)
        layout.addWidget(cache_group)

        # === 自动清理 ===
        self.auto_cleanup_check = QCheckBox("生成最终版后自动清理中间文件")
        self.auto_cleanup_check.setChecked(self.settings.get("auto_cleanup", "false") == "true")
        layout.addWidget(self.auto_cleanup_check)

        # === 保存/取消 ===
        btn_layout = QHBoxLayout()
        btn_save = QPushButton("保存")
        btn_save.setFixedHeight(32)
        btn_save.clicked.connect(self.accept)
        btn_cancel = QPushButton("取消")
        btn_cancel.setFixedHeight(32)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_save)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

    def get_settings(self):
        return {
            "api_key": self.api_key_edit.text().strip(),
            "api_url": self.api_url_edit.text().strip(),
            "model": self.model_edit.text().strip(),
            "ocr_engine": self.engine_combo.currentData(),
            "ocr_mode": self.mode_combo.currentData(),
            "auto_cleanup": "true" if self.auto_cleanup_check.isChecked() else "false",
        }

    def _test_api(self):
        """测试 API 连接"""
        import requests
        api_key = self.api_key_edit.text().strip()
        api_url = self.api_url_edit.text().strip()
        model = self.model_edit.text().strip()
        if not all([api_key, api_url, model]):
            self.api_status.setText("请先填写完整的 API 配置")
            self.api_status.setStyleSheet("color: #f44336;")
            return
        self.api_status.setText("测试中...")
        self.api_status.setStyleSheet("color: #888;")
        QApplication.processEvents()
        try:
            headers = {
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            }
            payload = {
                "model": model,
                "max_tokens": 32,
                "messages": [{"role": "user", "content": "请回复\"连接成功\""}],
            }
            resp = requests.post(api_url, headers=headers, json=payload, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            reply = ""
            for block in data.get("content", []):
                if block.get("type") == "text":
                    reply += block["text"]
            self.api_status.setText(f"连接成功！AI 回复: {reply.strip()}")
            self.api_status.setStyleSheet("color: #4CAF50;")
        except Exception as e:
            self.api_status.setText(f"连接失败: {e}")
            self.api_status.setStyleSheet("color: #f44336;")

    def _check_env(self):
        """逐项检测环境"""
        self.env_log.clear()
        checks = [
            ("Python", self._check_python),
            ("OpenCV", self._check_opencv),
            ("RapidOCR (CPU)", self._check_rapidocr),
            ("PaddleOCR 运行环境", self._check_paddle_runtime),
            ("CUDA 可用", self._check_cuda),
        ]
        for name, func in checks:
            self.env_log.append(f"检测 {name} ...")
            QApplication.processEvents()
            try:
                ok, detail = func()
                icon = "OK" if ok else "MISSING"
                self.env_log.append(f"  [{icon}] {name}: {detail}")
            except Exception as e:
                self.env_log.append(f"  [ERROR] {name}: {e}")
            self.env_log.append("")

    def _check_python(self):
        import sys
        return True, f"Python {sys.version.split()[0]}"

    def _check_opencv(self):
        import cv2
        return True, f"OpenCV {cv2.__version__}"

    def _check_rapidocr(self):
        try:
            try:
                from rapidocr import RapidOCR
            except ModuleNotFoundError:
                from rapidocr_onnxruntime import RapidOCR
            return True, "已安装 (CPU 模式)"
        except ImportError:
            return False, "未安装，请运行: pip install rapidocr-onnxruntime"

    def _check_paddle_runtime(self):
        try:
            import paddle
            try:
                import paddleocr  # noqa: F401
            except ImportError:
                return False, "PaddleOCR 未安装，请运行: python -m pip install paddleocr"
            try:
                import paddlex  # noqa: F401
            except ImportError:
                return False, "paddlex 未安装，请运行: python -m pip install \"paddlex[ocr]\""
            gpu = paddle.device.is_compiled_with_cuda()
            if gpu:
                return True, f"PaddlePaddle {paddle.__version__} (GPU)"
            return False, f"PaddlePaddle {paddle.__version__} (仅 CPU，GPU OCR 不可用)"
        except ImportError:
            return False, "未安装，请运行: python -m pip install paddlepaddle-gpu==3.3.0 paddleocr \"paddlex[ocr]\""
        except Exception as e:
            return False, f"检测失败: {e}"

    def _check_cuda(self):
        try:
            import subprocess
            result = subprocess.run(["nvidia-smi"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                # 提取 GPU 型号
                for line in result.stdout.split("\n"):
                    if "MiB" in line:
                        gpu_info = line.split("|")[1].strip()
                        return True, gpu_info
                return True, "nvidia-smi 可用"
            else:
                return False, "nvidia-smi 不可用"
        except FileNotFoundError:
            return False, "未安装 NVIDIA 驱动"
        except Exception as e:
            return False, str(e)

    def _clear_cache(self):
        cache_dir = os.path.join(get_app_dir(), "cache")
        if not os.path.isdir(cache_dir):
            QMessageBox.information(self, "提示", "没有找到缓存目录")
            return
        frames_dirs = []
        for d in os.listdir(cache_dir):
            full = os.path.join(cache_dir, d)
            if os.path.isdir(full) and d.endswith("_frames"):
                frames_dirs.append(full)

        if not frames_dirs:
            QMessageBox.information(self, "提示", "没有找到缓存目录")
            return

        to_delete = []
        for frames_dir in frames_dirs:
            for item in os.listdir(frames_dir):
                if item.endswith("-最终版.txt"):
                    continue
                full = os.path.join(frames_dir, item)
                to_delete.append(full)

        if not to_delete:
            QMessageBox.information(self, "提示", "没有找到可清除的缓存文件")
            return
        reply = QMessageBox.question(
            self, "确认清除",
            f"将删除以下内容：\n" + "\n".join(os.path.basename(p) for p in to_delete),
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            for p in to_delete:
                if os.path.isdir(p):
                    shutil.rmtree(p)
                else:
                    os.remove(p)
            QMessageBox.information(self, "完成", "缓存已清除")


def detect_center_region(frame):
    """检测帧中字幕卡片区域。

    策略：用 Sobel 水平边缘找到字幕卡片的上下边界。
    字幕卡片是纯色块，和复杂背景之间有极强的水平边缘。
    只看横跨画面宽度 ≥50% 的边缘行（排除局部噪点）。
    """
    h, w = frame.shape[:2]
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Sobel 水平边缘
    sobel_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    abs_sobel = np.abs(sobel_y)

    # 只看中间 20%-80%
    search_top = int(h * 0.20)
    search_bottom = int(h * 0.80)

    # 每行：统计边缘强度超过阈值的列数占比（横跨宽度）
    row_threshold = np.percentile(abs_sobel, 80)
    edge_width_ratio = np.mean(abs_sobel > row_threshold, axis=1)

    # 只保留横跨 ≥50% 宽度的行
    wide_mask = edge_width_ratio >= 0.50
    mid_mask = wide_mask[search_top:search_bottom]

    # 聚类通过的行（间距 < 10px 的算一组）
    passed_rows = np.where(mid_mask)[0] + search_top
    if len(passed_rows) < 2:
        return (0.0, 0.25, 1.0, 0.5)

    clusters = []
    start = passed_rows[0]
    for i in range(1, len(passed_rows)):
        if passed_rows[i] - passed_rows[i-1] > 10:
            clusters.append((start, passed_rows[i-1]))
            start = passed_rows[i]
    clusters.append((start, passed_rows[-1]))

    # 取每个聚类的中心线和综合得分（宽度比 × 边缘强度）
    cluster_info = []
    for c_start, c_end in clusters:
        center = (c_start + c_end) // 2
        max_ratio = np.max(edge_width_ratio[c_start:c_end+1])
        mean_strength = np.mean(abs_sobel[c_start:c_end+1, :])
        score = max_ratio * mean_strength
        cluster_info.append((center, score))

    if len(cluster_info) < 2:
        return (0.0, 0.25, 1.0, 0.5)

    # 按综合得分排序，选最强的两个
    cluster_info.sort(key=lambda x: x[1], reverse=True)
    top_edge = min(cluster_info[0][0], cluster_info[1][0])
    bottom_edge = max(cluster_info[0][0], cluster_info[1][0])

    if bottom_edge - top_edge < 10:
        return (0.0, 0.25, 1.0, 0.5)

    return (0.0, top_edge / h, 1.0, (bottom_edge - top_edge) / h)


def detect_stable_region(frames_dir, sample_count=16):
    """从帧目录多帧采样，投票取最稳定区域。

    多数帧会给出正确结果，少数帧误检。用聚类投票选出正确结果。
    """
    files = sorted([f for f in os.listdir(frames_dir)
                    if f.startswith("frame_") and f.endswith(".png")])
    if not files:
        return (0.0, 0.25, 1.0, 0.5)

    step = max(1, len(files) // sample_count)
    sampled = files[::step][:sample_count]

    regions = []
    for fname in sampled:
        frame = _read_frame(os.path.join(frames_dir, fname))
        if frame is not None:
            r = detect_center_region(frame)
            if 0.05 <= r[3] <= 0.50:
                regions.append(r)

    if len(regions) < 2:
        return (0.0, 0.25, 1.0, 0.5)

    # 按 y 值聚类（间距 < 0.10 算一组）
    regions.sort(key=lambda r: r[1])
    groups = [[regions[0]]]
    for r in regions[1:]:
        if r[1] - groups[-1][-1][1] < 0.10:
            groups[-1].append(r)
        else:
            groups.append([r])

    # 选最大的组
    largest = max(groups, key=len)
    ys = sorted([r[1] for r in largest])
    hs = sorted([r[3] for r in largest])
    return (0.0, ys[len(ys) // 2], 1.0, hs[len(hs) // 2])


def get_app_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


class FrameExtractorGUI(QMainWindow):
    DEFAULT_SETTINGS = {
        "api_key": "",
        "api_url": "https://token-plan-cn.xiaomimimo.com/anthropic/v1/messages",
        "model": "mimo-v2.5-pro",
        "ocr_engine": "auto",
        "ocr_mode": "auto",
        "auto_cleanup": "true",
    }

    def __init__(self):
        super().__init__()
        self.setWindowTitle("帧提取工具")
        self.setMinimumSize(640, 520)
        icon_path = os.path.join(get_app_dir(), 'icon.ico')
        if os.path.exists(icon_path):
            from PySide6.QtGui import QIcon
            self.setWindowIcon(QIcon(icon_path))
        self.worker = None
        self._config_path = os.path.join(get_app_dir(), "config.json")
        self.settings = self._load_settings()
        self._init_ui()

    def _load_settings(self):
        s = dict(self.DEFAULT_SETTINGS)
        if os.path.exists(self._config_path):
            try:
                with open(self._config_path, 'r', encoding='utf-8') as f:
                    saved = json.load(f)
                for key in s:
                    if key in saved:
                        s[key] = saved[key]
            except Exception:
                pass
        return s

    def _save_settings(self):
        try:
            with open(self._config_path, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 20, 24, 20)

        # --- 顶部栏：设置按钮 ---
        top_bar = QHBoxLayout()
        top_bar.addStretch()
        btn_settings = QPushButton("设置")
        btn_settings.setFixedWidth(60)
        btn_settings.setFixedHeight(28)
        btn_settings.clicked.connect(self._open_settings)
        top_bar.addWidget(btn_settings)
        layout.addLayout(top_bar)

        # --- 视频选择 ---
        video_group = QGroupBox("视频文件")
        video_layout = QHBoxLayout(video_group)
        self.video_path_label = QLabel("未选择")
        self.video_path_label.setStyleSheet("color: #888;")
        btn_select_video = QPushButton("选择视频")
        btn_select_video.setFixedWidth(100)
        btn_select_video.clicked.connect(self._select_video)
        video_layout.addWidget(self.video_path_label, 1)
        video_layout.addWidget(btn_select_video)
        layout.addWidget(video_group)

        # --- 进度条 ---
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(8)
        layout.addWidget(self.progress_bar)

        # --- 控制按钮 ---
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        self.btn_smart = QPushButton("一键提取")
        self.btn_smart.setFixedHeight(40)
        self.btn_smart.setStyleSheet(
            "QPushButton { background-color: #4CAF50; color: white; font-weight: bold; border-radius: 4px; }"
            "QPushButton:hover { background-color: #43A047; }"
            "QPushButton:disabled { background-color: #aaa; }"
        )
        self.btn_smart.clicked.connect(self._smart_extract)
        self.btn_stop = QPushButton("停止")
        self.btn_stop.setFixedHeight(40)
        self.btn_stop.setEnabled(False)
        self.btn_stop.setStyleSheet(
            "QPushButton { background-color: #f44336; color: white; border-radius: 4px; }"
            "QPushButton:hover { background-color: #e53935; }"
            "QPushButton:disabled { background-color: #ccc; color: #999; }"
        )
        self.btn_stop.clicked.connect(self._stop)
        btn_layout.addWidget(self.btn_smart)
        btn_layout.addWidget(self.btn_stop)
        layout.addLayout(btn_layout)

        # --- 日志 ---
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Menlo", 11))
        self.log_text.setStyleSheet("QTextEdit { background-color: #1e1e1e; color: #d4d4d4; border-radius: 4px; }")
        layout.addWidget(self.log_text, 1)

    def _open_settings(self):
        dialog = SettingsDialog(self.settings, parent=self)
        if dialog.exec() == QDialog.Accepted:
            self.settings = dialog.get_settings()
            self._save_settings()
            self.log_text.append("设置已保存")

    def _open_video(self):
        if not hasattr(self, '_safe_video'):
            self._safe_video, self._safe_tmp = _safe_open_path(self.video_path)
        return cv2.VideoCapture(self._safe_video)

    def _select_video(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "选择视频文件", "",
            "视频文件 (*.mp4 *.mkv *.avi *.flv *.mov *.wmv *.webm);;所有文件 (*)"
        )
        if not paths:
            return

        if len(paths) == 1:
            # 单视频模式
            _cleanup_safe_path(getattr(self, '_safe_tmp', None))
            self.video_path = paths[0]
            self._safe_video, self._safe_tmp = _safe_open_path(paths[0])
            self.video_path_label.setText(paths[0])
            self.video_path_label.setStyleSheet("")
            cache_dir = os.path.join(get_app_dir(), "cache")
            os.makedirs(cache_dir, exist_ok=True)
            self.output_path = os.path.join(cache_dir, Path(paths[0]).stem + "_frames")
            self._is_batch = False
        else:
            # 多视频：自动开启批处理
            self._batch_videos = list(paths)
            self._batch_index = 0
            self._batch_total = len(paths)
            self._is_batch = True
            self.video_path_label.setText(f"已选择 {len(paths)} 个视频（批处理模式）")
            self.video_path_label.setStyleSheet("")

    def _run_next_batch_video(self):
        """处理批处理队列中的下一个视频"""
        if self._batch_index >= self._batch_total:
            # 全部完成
            elapsed = time.time() - self._start_time
            minutes = int(elapsed // 60)
            seconds = elapsed % 60
            self.log_text.append(f"\n{'='*40}")
            self.log_text.append(f"批处理全部完成! 共 {self._batch_total} 个视频")
            if minutes > 0:
                self.log_text.append(f"总耗时: {minutes}分{seconds:.1f}秒")
            else:
                self.log_text.append(f"总耗时: {seconds:.1f}秒")
            self.log_text.append(f"{'='*40}")
            self.btn_smart.setEnabled(True)
            self.btn_stop.setEnabled(False)

            # 打开最后一个视频的输出目录
            last_video = self._batch_videos[-1]
            last_output = os.path.join(get_app_dir(), "cache",
                                       Path(last_video).stem + "_frames")
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("批处理完成")
            msg_box.setText(f"共处理 {self._batch_total} 个视频")
            btn_folder = msg_box.addButton("打开最后输出目录", QMessageBox.AcceptRole)
            msg_box.addButton("关闭", QMessageBox.RejectRole)
            msg_box.exec()
            if msg_box.clickedButton() == btn_folder:
                QDesktopServices.openUrl(QUrl.fromLocalFile(last_output))
            return

        video_path = self._batch_videos[self._batch_index]
        _cleanup_safe_path(getattr(self, '_safe_tmp', None))
        self.video_path = video_path
        self._safe_video, self._safe_tmp = _safe_open_path(video_path)
        cache_dir = os.path.join(get_app_dir(), "cache")
        os.makedirs(cache_dir, exist_ok=True)
        self.output_path = os.path.join(cache_dir, Path(video_path).stem + "_frames")
        self._region = None

        self.log_text.append(f"\n{'='*40}")
        self.log_text.append(f"[{self._batch_index+1}/{self._batch_total}] {os.path.basename(video_path)}")
        self.log_text.append(f"{'='*40}")

        cap = self._open_video()
        if cap.isOpened():
            total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            vfps = cap.get(cv2.CAP_PROP_FPS)
            dur = total / vfps if vfps > 0 else 0
            self.log_text.append(f"视频: {dur:.0f}秒, {vfps:.0f}fps, {total}帧")
            cap.release()

        self.progress_bar.setValue(0)
        self.btn_smart.setEnabled(False)
        self.btn_stop.setEnabled(True)

        self.worker = SmartExtractWorker(video_path, self.output_path, 9, 0.3)
        self.worker.progress.connect(self._on_progress)
        self.worker.log.connect(self._on_log)
        self.worker.finished.connect(self._on_smart_finished)
        self.worker.start()

    def _stop(self):
        if self.worker:
            self.worker.stop()
        # 批处理模式下停止整个批处理
        if getattr(self, '_is_batch', False):
            self._is_batch = False
            self.btn_smart.setEnabled(True)
            self.btn_stop.setEnabled(False)
            self.log_text.append("\n批处理已停止")

    def _on_progress(self, current, total):
        pct = int(current / total * 100) if total > 0 else 0
        self.progress_bar.setValue(pct)

    def _on_log(self, msg):
        self.log_text.append(msg)

    def _smart_extract(self):
        # 批处理模式
        if getattr(self, '_is_batch', False):
            self._start_time = time.time()
            self._batch_index = 0
            self.log_text.clear()
            self.log_text.append(f"批处理模式: 共 {self._batch_total} 个视频")
            for i, p in enumerate(self._batch_videos):
                self.log_text.append(f"  {i+1}. {os.path.basename(p)}")
            self.log_text.append("")
            self._run_next_batch_video()
            return

        # 单视频模式
        if not hasattr(self, 'video_path'):
            self.log_text.append("请先选择视频文件")
            return

        self._start_time = time.time()
        self._region = None

        cap = self._open_video()
        if cap.isOpened():
            total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            vfps = cap.get(cv2.CAP_PROP_FPS)
            dur = total / vfps if vfps > 0 else 0
            self.log_text.clear()
            self.log_text.append(f"视频: {dur:.0f}秒, {vfps:.0f}fps, {total}帧")
            self.log_text.append(f"粗扫帧率: 9fps | 每个峰值只取1帧")
            cap.release()

        self.progress_bar.setValue(0)
        self.btn_smart.setEnabled(False)
        self.btn_stop.setEnabled(True)

        self.worker = SmartExtractWorker(self.video_path, self.output_path, 9, 0.3)
        self.worker.progress.connect(self._on_progress)
        self.worker.log.connect(self._on_log)
        self.worker.finished.connect(self._on_smart_finished)
        self.worker.start()

    def _detect_region_from_selected(self):
        """从最终提取帧中检测 OCR 区域（粗扫帧和提取帧不同，必须用提取帧检测）"""
        selected_dir = os.path.join(self.output_path, "selected")
        if not os.path.isdir(selected_dir):
            selected_dir = self.output_path

        ocr_mode = self.settings.get("ocr_mode", "auto")

        if ocr_mode == "auto":
            self.log_text.append("\n自动检测 OCR 区域...")
            try:
                self._region = detect_stable_region(selected_dir)
                self.log_text.append(
                    f"自动检测区域: x={self._region[0]:.2f} y={self._region[1]:.2f} "
                    f"w={self._region[2]:.2f} h={self._region[3]:.2f}")
            except Exception as e:
                self._region = None
                self.log_text.append(f"自动检测失败: {e}，将对全图 OCR")
        else:
            self.log_text.append("\n请选择 OCR 区域...")
            try:
                files = sorted([f for f in os.listdir(selected_dir)
                                if f.startswith("frame_") and f.endswith(".png")])
                sample_path = os.path.join(selected_dir, files[0]) if files else None
                if sample_path:
                    dialog = RegionSelectorDialog(sample_path, self)
                    if dialog.exec() == QDialog.Accepted:
                        self._region = dialog.region
                        if self._region:
                            self.log_text.append(
                                f"已选定区域: x={self._region[0]:.2f} y={self._region[1]:.2f} "
                                f"w={self._region[2]:.2f} h={self._region[3]:.2f}")
                        else:
                            self.log_text.append("未画选区，将对全图 OCR")
                    else:
                        self.log_text.append("已跳过区域选择，将对全图 OCR")
                else:
                    self.log_text.append("无提取帧，将对全图 OCR")
            except Exception as e:
                self.log_text.append(f"区域选择失败: {e}，将对全图 OCR")

    def _on_smart_finished(self, success, msg):
        self.progress_bar.setValue(100 if success else self.progress_bar.value())
        self.log_text.append(f"\n{'✓' if success else '✗'} {msg}")

        if not success:
            self.btn_smart.setEnabled(True)
            self.btn_stop.setEnabled(False)
            return

        # 智能提取完成，从提取帧检测区域后开始 OCR
        self._detect_region_from_selected()
        self._start_ocr()

    def _start_ocr(self):
        """启动批量 OCR（使用存储的区域）"""
        selected_dir = os.path.join(self.output_path, "selected")
        ocr_input = selected_dir if os.path.isdir(selected_dir) else self.output_path

        ocr_output = os.path.join(self.output_path, "ocr_results.txt")
        self.log_text.append(f"\n{'='*40}")
        self.log_text.append(f"批量 OCR: {ocr_input}")
        if self._region:
            self.log_text.append(f"区域: x={self._region[0]:.2f} y={self._region[1]:.2f} "
                                 f"w={self._region[2]:.2f} h={self._region[3]:.2f}")
        else:
            self.log_text.append("区域: 全图")
        self.log_text.append(f"{'='*40}")

        self.progress_bar.setValue(0)

        engine_type = self.settings.get("ocr_engine", "auto")
        self.worker = BatchOCRWorker(ocr_input, ocr_output, self._region, engine_type)
        self.worker.progress.connect(self._on_progress)
        self.worker.log.connect(self._on_log)
        self.worker.finished.connect(self._on_ocr_finished)
        self.worker.start()

    def _on_ocr_finished(self, success, msg):
        self.progress_bar.setValue(100 if success else self.progress_bar.value())
        self.log_text.append(f"\n{'✓' if success else '✗'} {msg}")

        if not success:
            self.btn_smart.setEnabled(True)
            self.btn_stop.setEnabled(False)
            return

        # OCR 完成，先本地合并去重
        ocr_path = os.path.join(self.output_path, "ocr_results.txt")
        merged_path = os.path.join(self.output_path, "ocr-最终版.txt")
        video_stem = Path(self.video_path).stem
        final_path = os.path.join(self.output_path, f"{video_stem}-最终版.txt")

        self.log_text.append(f"\n{'='*40}")
        self.log_text.append("本地合并去重...")
        self.log_text.append(f"{'='*40}")

        try:
            from merge_ocr import parse_ocr_file, merge_frames
            frames = parse_ocr_file(ocr_path)
            merged = merge_frames(frames)

            with open(merged_path, 'w', encoding='utf-8') as f:
                for text in merged:
                    f.write(f"{text}\n")

            self.log_text.append(f"合并完成: {len(frames)} 帧 → {len(merged)} 条")
        except Exception as e:
            self.log_text.append(f"合并失败: {e}，使用原始 OCR 结果")
            merged_path = ocr_path

        # 读取合并后的内容发给 AI
        try:
            with open(merged_path, 'r', encoding='utf-8') as f:
                ocr_text = f.read()
        except Exception as e:
            self.log_text.append(f"读取合并结果失败: {e}")
            self.btn_smart.setEnabled(True)
            self.btn_stop.setEnabled(False)
            return

        self.log_text.append(f"\n{'='*40}")
        self.log_text.append("AI 纠错润色...")
        self.log_text.append(f"{'='*40}")

        worker = AICleanupWorker(ocr_text, final_path)
        worker.API_URL = self.settings.get("api_url", AICleanupWorker.API_URL)
        worker.API_KEY = self.settings.get("api_key", AICleanupWorker.API_KEY)
        worker.MODEL = self.settings.get("model", AICleanupWorker.MODEL)
        worker.log.connect(self._on_log)
        worker.finished.connect(self._on_ai_finished)
        self.worker = worker
        self.worker.start()

    def _auto_cleanup_output(self):
        if not self.output_path or not os.path.isdir(self.output_path):
            return
        removed = 0
        for item in os.listdir(self.output_path):
            if item.endswith("-最终版.txt"):
                continue
            full = os.path.join(self.output_path, item)
            try:
                if os.path.isdir(full):
                    shutil.rmtree(full)
                else:
                    os.remove(full)
                removed += 1
            except Exception:
                pass
        if removed:
            self.log_text.append(f"自动清理：删除了 {removed} 个中间文件")

    def _on_ai_finished(self, success, msg):
        self.progress_bar.setValue(100 if success else self.progress_bar.value())
        self.log_text.append(f"\n{'✓' if success else '✗'} {msg}")

        if success and self.settings.get("auto_cleanup", "false") == "true":
            self._auto_cleanup_output()

        # 批处理模式：自动处理下一个视频
        if getattr(self, '_is_batch', False):
            if success:
                self._batch_index += 1
            else:
                self.log_text.append(f"跳过失败的视频，继续处理下一个")
                self._batch_index += 1
            self._run_next_batch_video()
            return

        # 单视频模式
        self.btn_smart.setEnabled(True)
        self.btn_stop.setEnabled(False)

        # 输出总耗时
        if hasattr(self, '_start_time'):
            elapsed = time.time() - self._start_time
            minutes = int(elapsed // 60)
            seconds = elapsed % 60
            if minutes > 0:
                self.log_text.append(f"\n总耗时: {minutes}分{seconds:.1f}秒")
            else:
                self.log_text.append(f"\n总耗时: {seconds:.1f}秒")

        if not success:
            return

        video_stem = Path(self.video_path).stem
        final_path = os.path.join(self.output_path, f"{video_stem}-最终版.txt")

        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("完成")
        msg_box.setText(f"已生成：{video_stem}-最终版.txt")
        btn_open = msg_box.addButton("打开文件", QMessageBox.AcceptRole)
        btn_folder = msg_box.addButton("打开文件夹", QMessageBox.ActionRole)
        msg_box.addButton("关闭", QMessageBox.RejectRole)
        msg_box.exec()

        if msg_box.clickedButton() == btn_open:
            QDesktopServices.openUrl(QUrl.fromLocalFile(final_path))
        elif msg_box.clickedButton() == btn_folder:
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.output_path))


if __name__ == "__main__":
    if os.environ.get("ZHENTIQU_SELF_CHECK") == "1":
        sys.exit(run_self_check(os.environ.get("ZHENTIQU_SELF_CHECK_OUTPUT")))
    app = QApplication(sys.argv)
    window = FrameExtractorGUI()
    window.show()
    app.exec()
