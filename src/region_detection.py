#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Sobel 边缘检测 + 投票机制：自动定位字幕区域"""

import os
import cv2
import numpy as np

from .frame_algorithms import _read_frame


def detect_center_region(frame):
    """检测帧中字幕卡片区域。用 Sobel 水平边缘找到上下边界。"""
    h, w = frame.shape[:2]
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    sobel_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    abs_sobel = np.abs(sobel_y)

    search_top = int(h * 0.20)
    search_bottom = int(h * 0.80)

    row_threshold = np.percentile(abs_sobel, 80)
    edge_width_ratio = np.mean(abs_sobel > row_threshold, axis=1)

    wide_mask = edge_width_ratio >= 0.50
    mid_mask = wide_mask[search_top:search_bottom]

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

    cluster_info = []
    for c_start, c_end in clusters:
        center = (c_start + c_end) // 2
        max_ratio = np.max(edge_width_ratio[c_start:c_end+1])
        mean_strength = np.mean(abs_sobel[c_start:c_end+1, :])
        score = max_ratio * mean_strength
        cluster_info.append((center, score))

    if len(cluster_info) < 2:
        return (0.0, 0.25, 1.0, 0.5)

    cluster_info.sort(key=lambda x: x[1], reverse=True)
    top_edge = min(cluster_info[0][0], cluster_info[1][0])
    bottom_edge = max(cluster_info[0][0], cluster_info[1][0])

    if bottom_edge - top_edge < 10:
        return (0.0, 0.25, 1.0, 0.5)

    return (0.0, top_edge / h, 1.0, (bottom_edge - top_edge) / h)


def detect_stable_region(frames_dir, sample_count=16):
    """从帧目录多帧采样，投票取最稳定区域。"""
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

    regions.sort(key=lambda r: r[1])
    groups = [[regions[0]]]
    for r in regions[1:]:
        if r[1] - groups[-1][-1][1] < 0.10:
            groups[-1].append(r)
        else:
            groups.append([r])

    largest = max(groups, key=len)
    ys = sorted([r[1] for r in largest])
    hs = sorted([r[3] for r in largest])
    return (0.0, ys[len(ys) // 2], 1.0, hs[len(hs) // 2])
