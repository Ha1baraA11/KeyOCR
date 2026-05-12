#!/usr/bin/env python3
"""测试脚本：在测试视频上运行转换点检测算法，评估覆盖率"""

import os
import sys
import time
import shutil
import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from frame_extractor_gui import (
    _compute_diffs,
    _find_transition_peaks,
    _extract_frame_number,
    _safe_open_path,
    _cleanup_safe_path,
)

# === 配置 ===
VIDEO_PATH = "/Users/zetazero/Downloads/测试.mp4"
OUTPUT_DIR = "/Users/zetazero/Downloads/测试OCR图集_smart"
COARSE_FPS = 9
MARGIN_SEC = 0.3
THRESH_MULT = 1.5
MIN_DIST = 7

# 正确答案（37 帧）
CORRECT = {
    "frame_000135.png", "frame_000210.png", "frame_000333.png", "frame_000405.png",
    "frame_000537.png", "frame_000609.png", "frame_000726.png", "frame_000822.png",
    "frame_000888.png", "frame_001014.png", "frame_001074.png", "frame_001194.png",
    "frame_001329.png", "frame_001458.png", "frame_001554.png", "frame_001662.png",
    "frame_001776.png", "frame_001914.png", "frame_002007.png", "frame_002091.png",
    "frame_002190.png", "frame_002331.png", "frame_002430.png", "frame_002511.png",
    "frame_002601.png", "frame_002718.png", "frame_002886.png", "frame_003033.png",
    "frame_003138.png", "frame_003234.png", "frame_003354.png", "frame_003528.png",
    "frame_003594.png", "frame_003651.png", "frame_003768.png", "frame_003903.png",
    "frame_004017.png",
}

TOLERANCE = 6  # ±6 帧误差


def _open_video_compat(video_path):
    safe_path, tmp_dir = _safe_open_path(video_path)
    cap = cv2.VideoCapture(safe_path)
    return cap, tmp_dir


def _imwrite_compat(path, image):
    if cv2.imwrite(path, image):
        return True
    try:
        ok, buf = cv2.imencode(os.path.splitext(path)[1] or '.png', image)
        if not ok:
            return False
        with open(path, 'wb') as f:
            f.write(buf.tobytes())
        return True
    except Exception:
        return False


def main():
    cap, tmp_dir = _open_video_compat(VIDEO_PATH)
    if not cap.isOpened():
        _cleanup_safe_path(tmp_dir)
        print(f"无法打开视频: {VIDEO_PATH}")
        return

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    video_fps = cap.get(cv2.CAP_PROP_FPS)
    duration = total_frames / video_fps
    print(f"视频: {total_frames} 帧, {video_fps:.1f}fps, {duration:.1f}s")

    # === 阶段1: 粗扫截帧 ===
    coarse_dir = os.path.join(OUTPUT_DIR, "coarse")
    if os.path.exists(coarse_dir):
        shutil.rmtree(coarse_dir)
    os.makedirs(coarse_dir)

    coarse_interval = max(1, int(video_fps / COARSE_FPS))
    print(f"\n阶段1: 粗扫截帧 (间隔={coarse_interval}帧, 等效{video_fps/coarse_interval:.1f}fps)")
    t0 = time.time()

    count = 0
    for i in range(0, total_frames, coarse_interval):
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ret, frame = cap.read()
        if ret:
            _imwrite_compat(os.path.join(coarse_dir, f"frame_{i:06d}.png"), frame)
            count += 1
    print(f"  结果: {count} 帧, 耗时 {time.time()-t0:.1f}s")

    # === 阶段2: 转换点检测 ===
    coarse_files = sorted([f for f in os.listdir(coarse_dir)
                           if f.startswith("frame_") and f.endswith(".png")])
    print(f"\n阶段2: 转换点检测")
    t0 = time.time()

    coarse_diffs = _compute_diffs(coarse_dir, coarse_files)
    nonzero = coarse_diffs[coarse_diffs > 0]
    median_diff = np.median(nonzero)

    peaks = _find_transition_peaks(coarse_diffs, thresh_mult=THRESH_MULT,
                                   min_dist_frames=MIN_DIST)
    print(f"  diff 中位数: {median_diff:.1f}")
    print(f"  阈值: {median_diff * THRESH_MULT:.1f} ({THRESH_MULT}x)")
    print(f"  峰值数: {len(peaks)}")
    print(f"  耗时: {time.time()-t0:.1f}s")

    # === 阶段3: 提取峰值前的帧 ===
    selected_dir = os.path.join(OUTPUT_DIR, "selected")
    if os.path.exists(selected_dir):
        shutil.rmtree(selected_dir)
    os.makedirs(selected_dir)

    pre_margin = int(MARGIN_SEC * video_fps)
    print(f"\n阶段3: 提取峰值前 {MARGIN_SEC}s ({pre_margin}帧)")
    t0 = time.time()

    saved = set()
    for pidx in peaks:
        peak_frame = _extract_frame_number(coarse_files[pidx])
        start = max(0, peak_frame - pre_margin)
        for f in range(start, peak_frame + 1):
            if f not in saved:
                cap.set(cv2.CAP_PROP_POS_FRAMES, f)
                ret, frame = cap.read()
                if ret:
                    _imwrite_compat(os.path.join(selected_dir, f"frame_{f:06d}.png"), frame)
                    saved.add(f)
    print(f"  结果: {len(saved)} 帧, 耗时 {time.time()-t0:.1f}s")
    cap.release()
    _cleanup_safe_path(tmp_dir)

    # === 评估覆盖率 ===
    selected_files = set(os.listdir(selected_dir))
    selected_nums = set()
    for f in selected_files:
        num = _extract_frame_number(f)
        selected_nums.add(num)

    # 正确帧号
    correct_nums = set()
    for f in CORRECT:
        correct_nums.add(_extract_frame_number(f))

    # 检查每个正确帧是否被覆盖（±TOLERANCE）
    covered = 0
    missed = []
    for cn in sorted(correct_nums):
        found = False
        for sn in selected_nums:
            if abs(sn - cn) <= TOLERANCE:
                found = True
                break
        if found:
            covered += 1
        else:
            missed.append(cn)

    coverage = covered / len(correct_nums) * 100
    compression = len(saved) / total_frames * 100

    print(f"\n{'='*50}")
    print(f"评估结果:")
    print(f"  输出帧: {len(saved)} (原视频 {total_frames} 帧)")
    print(f"  压缩率: {compression:.1f}% ({total_frames/len(saved):.1f}x)")
    print(f"  覆盖率: {covered}/{len(correct_nums)} = {coverage:.1f}%")
    if missed:
        print(f"  漏掉帧: {['frame_%06d' % m for m in missed]}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
