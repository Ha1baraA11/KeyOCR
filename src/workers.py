#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""QThread 后台线程：智能提取、批量 OCR、AI 纠错"""

import sys
import os
import shutil
import time
import cv2
import numpy as np
from pathlib import Path
from PySide6.QtCore import QThread, Signal

from .ocr_engine import OCREngine
from .frame_algorithms import (
    _twopass_select, _find_transition_peaks, _compute_diffs,
    _read_frame, _safe_open_path, _cleanup_safe_path, _extract_frame_number,
)


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
    coarse_ready = Signal(str)

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
            min_dist_frames = 5
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
        try:
            _, buf = cv2.imencode('.png', frame)
            with open(path, 'wb') as f:
                f.write(buf.tobytes())
            return True
        except Exception:
            return False

    def _extract_frames(self, output_dir, interval, total_frames, video_fps):
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


class BatchOCRWorker(QThread):
    """批量 OCR：对目录中的图片逐张识别，输出合并文本"""
    progress = Signal(int, int)
    log = Signal(str)
    finished = Signal(bool, str)

    def __init__(self, input_dir, output_path, region=None, engine_type="auto"):
        super().__init__()
        self.input_dir = input_dir
        self.output_path = output_path
        self.region = region
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
                img = _read_frame(fpath)
                if img is None:
                    self.log.emit(f"[{i+1}/{len(files)}] {fname}: 读取失败，跳过")
                    results.append(f"=== {fname} ===\n(读取失败)")
                    self.progress.emit(i + 1, len(files))
                    continue

                if self.region:
                    h, w = img.shape[:2]
                    rx, ry, rw, rh = self.region
                    x1, y1 = int(rx * w), int(ry * h)
                    x2, y2 = int((rx + rw) * w), int((ry + rh) * h)
                    img = img[y1:y2, x1:x2]

                texts, scores = engine.ocr(img)

                if texts:
                    text = "\n".join(texts)
                    avg_score = (sum(scores) / len(scores)) if scores else 0.0
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

    DEFAULT_PROMPT = (
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
        "OCR 原文：\n{ocr_text}"
    )

    def __init__(self, ocr_text, output_path, prompt_template=None):
        super().__init__()
        self.ocr_text = ocr_text
        self.output_path = output_path
        self.prompt_template = prompt_template or self.DEFAULT_PROMPT
        self._running = True

    def run(self):
        try:
            import requests

            self.log.emit("正在调用 AI 纠错润色...")

            prompt = self.prompt_template.replace("{ocr_text}", self.ocr_text)

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

            ai_text = ""
            for block in data.get("content", []):
                if block.get("type") == "text":
                    ai_text += block["text"]

            if not ai_text.strip():
                self.finished.emit(False, "AI 返回为空")
                return

            with open(self.output_path, 'w', encoding='utf-8') as f:
                f.write(ai_text.strip() + "\n")

            self.log.emit(f"AI 纠错完成，已保存到 {os.path.basename(self.output_path)}")
            self.finished.emit(True, f"AI 纠错完成，已保存到 {os.path.basename(self.output_path)}")

        except Exception as e:
            self.finished.emit(False, f"AI 调用失败: {e}")

    def stop(self):
        self._running = False
