#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""主窗口 FrameExtractorGUI"""

import sys
import os
import json
import shutil
import time
import cv2
from pathlib import Path
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QFont, QDesktopServices
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QProgressBar, QTextEdit,
    QGroupBox, QDialog, QMessageBox,
)

from .ocr_engine import _can_use_paddle_gpu
from .frame_algorithms import _safe_open_path, _cleanup_safe_path
from .workers import SmartExtractWorker, BatchOCRWorker, AICleanupWorker
from .dialogs import SettingsDialog, RegionSelectorDialog, get_app_dir
from .region_detection import detect_stable_region


class FrameExtractorGUI(QMainWindow):
    DEFAULT_SETTINGS = {
        "api_key": "",
        "api_url": "https://token-plan-cn.xiaomimimo.com/anthropic/v1/messages",
        "model": "mimo-v2.5-pro",
        "ocr_engine": "auto",
        "ocr_mode": "auto",
        "auto_cleanup": "true",
        "ai_prompt": AICleanupWorker.DEFAULT_PROMPT,
    }

    def __init__(self):
        super().__init__()
        self.setWindowTitle("KeyOCR")
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
        if sys.platform == "win32" and s.get("ocr_engine") == "gpu" and not _can_use_paddle_gpu():
            s["ocr_engine"] = "auto"
        return s

    def _save_settings(self):
        try:
            with open(self._config_path, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _ensure_final_output_dir(self):
        final_dir = os.path.join(get_app_dir(), "最终版")
        os.makedirs(final_dir, exist_ok=True)
        return final_dir

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 20, 24, 20)

        # --- 顶部栏 ---
        top_bar = QHBoxLayout()
        top_bar.addStretch()
        btn_open_folder = QPushButton("打开文件夹")
        btn_open_folder.setFixedWidth(80)
        btn_open_folder.setFixedHeight(28)
        btn_open_folder.clicked.connect(self._open_final_output_folder)
        top_bar.addWidget(btn_open_folder)
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

    def _open_final_output_folder(self):
        final_dir = self._ensure_final_output_dir()
        QDesktopServices.openUrl(QUrl.fromLocalFile(final_dir))

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
            self._batch_videos = list(paths)
            self._batch_index = 0
            self._batch_total = len(paths)
            self._is_batch = True
            self.video_path_label.setText(f"已选择 {len(paths)} 个视频（批处理模式）")
            self.video_path_label.setStyleSheet("")

    def _run_next_batch_video(self):
        if self._batch_index >= self._batch_total:
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

            last_video = self._batch_videos[-1]
            last_output = os.path.join(get_app_dir(), "cache",
                                       Path(last_video).stem + "_frames")
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("批处理完成")
            msg_box.setText(f"共处理 {self._batch_total} 个视频")
            btn_final = msg_box.addButton("打开最终版文件夹", QMessageBox.AcceptRole)
            btn_folder = msg_box.addButton("打开最后缓存目录", QMessageBox.ActionRole)
            msg_box.addButton("关闭", QMessageBox.RejectRole)
            msg_box.exec()
            if msg_box.clickedButton() == btn_final:
                QDesktopServices.openUrl(QUrl.fromLocalFile(
                    os.path.join(get_app_dir(), "最终版")))
            elif msg_box.clickedButton() == btn_folder:
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

        self._detect_region_from_selected()
        self._start_ocr()

    def _start_ocr(self):
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

        worker = AICleanupWorker(ocr_text, final_path,
                                  prompt_template=self.settings.get("ai_prompt", AICleanupWorker.DEFAULT_PROMPT))
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

        if success:
            try:
                final_dir = self._ensure_final_output_dir()
                video_stem = Path(self.video_path).stem
                src = os.path.join(self.output_path, f"{video_stem}-最终版.txt")
                if os.path.exists(src):
                    dst = os.path.join(final_dir, f"{video_stem}-最终版.txt")
                    shutil.copy2(src, dst)
                    self.log_text.append(f"已复制到: {dst}")
            except Exception as e:
                self.log_text.append(f"复制最终版失败: {e}")

        if getattr(self, '_is_batch', False):
            if success:
                self._batch_index += 1
            else:
                self.log_text.append(f"跳过失败的视频，继续处理下一个")
                self._batch_index += 1
            self._run_next_batch_video()
            return

        self.btn_smart.setEnabled(True)
        self.btn_stop.setEnabled(False)

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
        btn_final = msg_box.addButton("打开最终版文件夹", QMessageBox.ActionRole)
        btn_folder = msg_box.addButton("打开缓存文件夹", QMessageBox.ActionRole)
        msg_box.addButton("关闭", QMessageBox.RejectRole)
        msg_box.exec()

        if msg_box.clickedButton() == btn_open:
            QDesktopServices.openUrl(QUrl.fromLocalFile(final_path))
        elif msg_box.clickedButton() == btn_final:
            QDesktopServices.openUrl(QUrl.fromLocalFile(
                os.path.join(get_app_dir(), "最终版")))
        elif msg_box.clickedButton() == btn_folder:
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.output_path))
