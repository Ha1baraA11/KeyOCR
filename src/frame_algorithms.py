#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""帧差计算、转换点检测、图像 IO 工具函数"""

import sys
import os
import tempfile
import shutil
import cv2
import numpy as np


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
    """两遍选择: 第一遍严格高置信, 第二遍宽松补充"""
    nonzero = diffs[diffs > 0]
    if len(nonzero) == 0:
        return []

    median_diff = np.median(nonzero)
    n = len(files)

    pm = np.percentile(nonzero, 85)
    nm1 = median_diff * 1.25
    nm2 = median_diff * 1.0

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
    """检测转换峰值: next_diff 超过中位数 × thresh_mult 的局部最大值"""
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
    """Windows 中文路径兼容：创建临时符号链接到纯英文路径"""
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
        try:
            buf = ctypes.create_unicode_buffer(512)
            if ctypes.windll.kernel32.GetShortPathNameW(path, buf, 512):
                return buf.value, None
        except Exception:
            pass
        print(f"[WARNING] 中文路径兼容失败: {path}", file=sys.stderr)
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
