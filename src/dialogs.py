#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Qt 对话框：区域选择器 + 设置"""

import os
import shutil
import cv2
from PySide6.QtCore import Qt, QPoint, QRect
from PySide6.QtGui import QFont, QPixmap, QImage, QPainter, QPen, QColor
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QLineEdit, QTextEdit, QGroupBox, QMessageBox, QComboBox,
    QCheckBox, QApplication,
)

from .frame_algorithms import _read_frame
from .ocr_engine import _import_status, run_self_check


def get_app_dir():
    import sys
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class RegionSelectorDialog(QDialog):
    """区域选择对话框：显示示例帧，用户拖拽选定 OCR 区域"""

    def __init__(self, image_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("选择 OCR 区域")
        self.setMinimumSize(800, 600)

        img = _read_frame(image_path)
        if img is None:
            raise ValueError(f"无法加载图片: {image_path}")
        h, w, ch = img.shape
        bytes_per_line = ch * w
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        qimg = QImage(img_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
        self.original_pixmap = QPixmap.fromImage(qimg.copy())

        self.orig_w = self.original_pixmap.width()
        self.orig_h = self.original_pixmap.height()

        self._selecting = False
        self._start_pos = None
        self._rect = QRect()
        self.region = None

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
        available = self.image_label.size()
        scaled = self.original_pixmap.scaled(
            available, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self._scale_w = scaled.width()
        self._scale_h = scaled.height()

        canvas = scaled.copy()
        if not self._rect.isNull() and self._rect.width() > 0 and self._rect.height() > 0:
            painter = QPainter(canvas)
            pen = QPen(QColor(255, 0, 0), 2, Qt.SolidLine)
            painter.setPen(pen)
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
            rx = self._rect.x() / self._scale_w
            ry = self._rect.y() / self._scale_h
            rw = self._rect.width() / self._scale_w
            rh = self._rect.height() / self._scale_h
            self.region = (rx, ry, rw, rh)
        self.accept()


class SettingsDialog(QDialog):
    """设置对话框：API 配置、环境检测、缓存管理"""

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setMinimumWidth(500)
        self.setMinimumHeight(500)
        self.settings = dict(settings)

        from .workers import AICleanupWorker

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

        # === AI 提示词 ===
        ai_prompt_group = QGroupBox("AI 提示词")
        ai_prompt_layout = QVBoxLayout(ai_prompt_group)
        ai_prompt_layout.addWidget(QLabel("自定义 AI 纠错润色的提示词模板，使用 {ocr_text} 作为 OCR 文本占位符"))
        self.ai_prompt_edit = QTextEdit()
        self.ai_prompt_edit.setMinimumHeight(180)
        self.ai_prompt_edit.setPlainText(self.settings.get("ai_prompt", AICleanupWorker.DEFAULT_PROMPT))
        ai_prompt_layout.addWidget(self.ai_prompt_edit)
        layout.addWidget(ai_prompt_group)

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
            "ai_prompt": self.ai_prompt_edit.toPlainText().strip(),
        }

    def _test_api(self):
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
