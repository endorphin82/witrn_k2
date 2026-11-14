"""Native desktop GUI for WITRN K2 using PyQt6 + pyqtgraph."""
from __future__ import annotations

import json
import sys
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QAction, QFont, QPalette
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog,
    QGridLayout, QGroupBox, QHBoxLayout, QLabel, QMainWindow, QMessageBox,
    QProgressBar, QPushButton, QSpinBox, QSplitter, QTabWidget,
    QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
)

import numpy as np
import pyqtgraph as pg

from .core.analytics import build_report, calculate_statistics, detect_peaks, detect_phases, moving_average
from .core.exporter import (
    export_json, export_official_csv, export_standard_csv,
    import_official_csv, read_sqlite_samples,
)
from .core.recorder import AutoStopRule, Recorder
from .core.svgcharts import export_samples_svg
from .core.telemetry import Sample, decode_report
from .core.transport import find_k2_device, open_transport


# ── Dark lab theme ──────────────────────────────────────────────────────────
DARK_STYLE = """
QWidget {
    background-color: #1a1a2e;
    color: #e0e0e0;
    font-family: 'Segoe UI', 'Ubuntu', sans-serif;
    font-size: 13px;
}
QGroupBox {
    border: 1px solid #16213e;
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 14px;
    font-weight: bold;
    color: #00d2ff;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
}
QPushButton {
    background-color: #0f3460;
    border: 1px solid #16213e;
    border-radius: 5px;
    padding: 6px 18px;
    font-weight: bold;
    color: #e0e0e0;
}
QPushButton:hover { background-color: #1a508b; }
QPushButton:pressed { background-color: #0a2647; }
QPushButton:disabled { background-color: #222; color: #666; }
QPushButton#recBtn { background-color: #e94560; }
QPushButton#recBtn:hover { background-color: #ff6b81; }
QPushButton#stopBtn { background-color: #533483; }
QLabel#bigVal { font-size: 32px; font-weight: bold; }
QLabel#metricTitle { font-size: 11px; color: #888; text-transform: uppercase; }
QComboBox, QSpinBox, QDoubleSpinBox {
    background-color: #16213e;
    border: 1px solid #0f3460;
    border-radius: 4px;
    padding: 4px 8px;
    color: #e0e0e0;
}
QCheckBox { spacing: 8px; }
QCheckBox::indicator { width: 16px; height: 16px; border: 1px solid #0f3460; border-radius: 3px; background: #16213e; }
QCheckBox::indicator:checked { background: #00d2ff; }
QSplitter::handle { background: #16213e; width: 2px; }
QTabWidget::pane { border: 1px solid #16213e; }
QTabBar::tab { background: #0f3460; padding: 6px 16px; margin-right: 2px; border-top-left-radius: 4px; border-top-right-radius: 4px; }
QTabBar::tab:selected { background: #1a1a2e; color: #00d2ff; }
QTableWidget { background-color: #13132b; gridline-color: #16213e; }
QHeaderView::section { background-color: #0f3460; color: #00d2ff; padding: 4px; border: none; }
QTextEdit { background-color: #13132b; border: 1px solid #16213e; font-family: 'Consolas', 'monospace'; font-size: 12px; }
QListWidget { background-color: #13132b; border: 1px solid #16213e; }
QListWidget::item:selected { background: #0f3460; color: #00d2ff; }
QMenuBar { background-color: #0f3460; color: #e0e0e0; }
QMenuBar::item:selected { background: #1a508b; }
QMenu { background-color: #16213e; border: 1px solid #0f3460; }
QMenu::item:selected { background: #0f3460; }
"""


# ── Background reader thread ────────────────────────────────────────────────
class DeviceThread(QThread):
    sample_ready = pyqtSignal(object)
    error = pyqtSignal(str)
    connected = pyqtSignal(dict)

    def __init__(self, simulator: bool = True):
        super().__init__()
        self._simulator = simulator
        self._running = False
        self._trans = None
        self._started = 0.0

    def run(self):
        self._running = True
        try:
            trans, info = open_transport(force_simulator=self._simulator)
            self._trans = trans
            self._started = time.monotonic()
            self.connected.emit(info)
        except Exception as exc:
            self.error.emit(str(exc))
            return

        while self._running:
            try:
                raw = self._trans.read(20)
                if raw:
                    elapsed = time.monotonic() - self._started
                    sample = decode_report(raw, elapsed)
                    if sample:
                        self.sample_ready.emit(sample)
            except Exception as exc:
                self.error.emit(str(exc))
                break
            self.msleep(5)

        if self._trans:
            try:
                self._trans.close()
            except Exception:
                pass

    def stop(self):
        self._running = False
        self.wait(2000)


# ── Metric card widget ──────────────────────────────────────────────────────
class MetricCard(QWidget):
    def __init__(self, title: str, unit: str, color: str = "#00d2ff", fmt: str = ".4f"):
        super().__init__()
        self._fmt = fmt
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 6, 12, 6)
        lay.setSpacing(1)
        self._title = QLabel(title.upper())
        self._title.setObjectName("metricTitle")
        lay.addWidget(self._title)
        self._value = QLabel("—")
        self._value.setObjectName("bigVal")
        self._value.setStyleSheet(f"color: {color};")
        lay.addWidget(self._value)
        self._extra = QLabel("")
        self._extra.setStyleSheet("color: #888; font-size: 11px;")
        lay.addWidget(self._extra)
        self.setStyleSheet(
            f"background-color: #16213e; border-radius: 8px; border-left: 3px solid {color};"
        )

    def set_value(self, val: Optional[float], extra: str = ""):
        self._value.setText(format(val, self._fmt) if val is not None else "—")
        self._extra.setText(extra)


# ── Helper: moving average ──────────────────────────────────────────────────
# ── Shared analysis helpers (core) ──────────────────────────────────────────
_moving_average = moving_average
_detect_peaks = detect_peaks


# ── Main window ─────────────────────────────────────────────────────────────
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("⚡ WITRN K2 — Лабораторний аналізатор")
        self.setMinimumSize(1200, 780)
        self.setStyleSheet(DARK_STYLE)

        # Live data buffers
        self._buf_t: deque = deque(maxlen=3000)
        self._buf_v: deque = deque(maxlen=3000)
        self._buf_i: deque = deque(maxlen=3000)
        self._buf_p: deque = deque(maxlen=3000)
        self._all_samples: list[Sample] = []
        self._recorder: Optional[Recorder] = None
        self._thread: Optional[DeviceThread] = None
        self._last_sample: Optional[Sample] = None

        # Loaded / reference data
        self._loaded_samples: list[Sample] = []
        self._ref_samples: list[Sample] = []
        self._loaded_name: str = ""
        self._ref_name: str = ""

        # Analysis state
        self._ma_window: int = 10
        self._show_peaks: bool = False
        self._show_cursor: bool = True

        self._build_ui()
        self._build_menu()
        self._init_plots()

        self._ui_timer = QTimer(self)
        self._ui_timer.timeout.connect(self._refresh_ui)
        self._ui_timer.start(66)

        self._stats_timer = QTimer(self)
        self._stats_timer.timeout.connect(self._refresh_stats)
        self._stats_timer.start(1000)

    # ── Menu bar ────────────────────────────────────────────────────────────
    def _build_menu(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu("Файл")
        act_load = QAction("📂 Завантажити запис…", self)
        act_load.setShortcut("Ctrl+O")
        act_load.triggered.connect(self._on_load_file)
        file_menu.addAction(act_load)

        act_load_csv = QAction("📂 Завантажити CSV…", self)
        act_load_csv.setShortcut("Ctrl+Shift+O")
        act_load_csv.triggered.connect(self._on_load_csv)
        file_menu.addAction(act_load_csv)

        file_menu.addSeparator()

        act_export_witrn = QAction("💾 Експорт WITRN CSV…", self)
        act_export_witrn.setShortcut("Ctrl+S")
        act_export_witrn.triggered.connect(lambda: self._on_export("witrn_csv"))
        file_menu.addAction(act_export_witrn)

        act_export_std = QAction("💾 Експорт стандартний CSV…", self)
        act_export_std.setShortcut("Ctrl+Shift+S")
        act_export_std.triggered.connect(lambda: self._on_export("standard_csv"))
        file_menu.addAction(act_export_std)

        act_export_json = QAction("💾 Експорт JSON…", self)
        act_export_json.setShortcut("Ctrl+J")
        act_export_json.triggered.connect(lambda: self._on_export("json"))
        file_menu.addAction(act_export_json)

        file_menu.addSeparator()
        act_svg = QAction("📐 Експорт графіків у SVG (вектор)…", self)
        act_svg.setShortcut("Ctrl+Shift+V")
        act_svg.triggered.connect(self._on_export_svg)
        file_menu.addAction(act_svg)

        file_menu.addSeparator()
        act_report = QAction("📝 Генерувати звіт…", self)
        act_report.setShortcut("Ctrl+R")
        act_report.triggered.connect(self._on_generate_report)
        file_menu.addAction(act_report)

        file_menu.addSeparator()
        act_quit = QAction("Вихід", self)
        act_quit.setShortcut("Ctrl+Q")
        act_quit.triggered.connect(self.close)
        file_menu.addAction(act_quit)

        view_menu = menubar.addMenu("Вигляд")

        self._act_cursor = QAction("Курсор (crosshair)", self, checkable=True, checked=True)
        self._act_cursor.setShortcut("C")
        self._act_cursor.toggled.connect(self._toggle_cursor)
        view_menu.addAction(self._act_cursor)

        self._act_ma = QAction("Ковзне середнє", self, checkable=True, checked=False)
        self._act_ma.setShortcut("M")
        self._act_ma.toggled.connect(self._toggle_ma)
        view_menu.addAction(self._act_ma)

        self._act_peaks = QAction("Детекція піків", self, checkable=True, checked=False)
        self._act_peaks.setShortcut("P")
        self._act_peaks.toggled.connect(self._toggle_peaks)
        view_menu.addAction(self._act_peaks)

        view_menu.addSeparator()
        act_reset = QAction("Скинути масштаб графіків", self)
        act_reset.setShortcut("Ctrl+0")
        act_reset.triggered.connect(self._reset_zoom)
        view_menu.addAction(act_reset)

        act_clear_live = QAction("Очистити живі дані", self)
        act_clear_live.setShortcut("Ctrl+Delete")
        act_clear_live.triggered.connect(self._on_clear_live)
        view_menu.addAction(act_clear_live)

        ref_menu = menubar.addMenu("Порівняння")
        act_ref = QAction("Завантажити референсну сесію…", self)
        act_ref.setShortcut("Ctrl+Shift+R")
        act_ref.triggered.connect(self._on_load_reference)
        ref_menu.addAction(act_ref)
        act_ref_clear = QAction("Очистити референс", self)
        act_ref_clear.setShortcut("Ctrl+Shift+D")
        act_ref_clear.triggered.connect(self._on_clear_reference)
        ref_menu.addAction(act_ref_clear)

        # ── Connection / recording global shortcuts ─────────────────────────
        act_connect = QAction(self)
        act_connect.setShortcut("F5")
        act_connect.triggered.connect(self._on_connect)
        self.addAction(act_connect)

        act_disconnect = QAction(self)
        act_disconnect.setShortcut("Escape")
        act_disconnect.triggered.connect(self._on_disconnect)
        self.addAction(act_disconnect)

        act_rec_toggle = QAction(self)
        act_rec_toggle.setShortcut("F9")
        act_rec_toggle.triggered.connect(self._on_record_toggle)
        self.addAction(act_rec_toggle)

        act_report = QAction(self)
        act_report.setShortcut("Ctrl+R")
        act_report.triggered.connect(self._on_generate_report)
        self.addAction(act_report)

        # ── Help menu ───────────────────────────────────────────────────────
        help_menu = menubar.addMenu("Довідка")
        act_shortcuts = QAction("⌨ Гарячі клавіші (F1)", self)
        act_shortcuts.setShortcut("F1")
        act_shortcuts.triggered.connect(self._show_shortcuts)
        help_menu.addAction(act_shortcuts)

    # ── UI construction ─────────────────────────────────────────────────────
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # Top toolbar
        top = QHBoxLayout()
        self._mode_combo = QComboBox()
        self._mode_combo.addItems(["Симулятор", "USB HID"])
        self._mode_combo.setMinimumWidth(150)
        self._mode_combo.setToolTip("Режим зв'язку: симулятор без пристрою або реальний USB HID")
        top.addWidget(QLabel("Режим:"))
        top.addWidget(self._mode_combo)

        self._connect_btn = QPushButton("🔌 Підключити")
        self._connect_btn.setToolTip("Підключити пристрій / симулятор  [F5]")
        self._connect_btn.clicked.connect(self._on_connect)
        top.addWidget(self._connect_btn)

        self._disconnect_btn = QPushButton("⏹ Відключити")
        self._disconnect_btn.setToolTip("Відключити пристрій  [Esc]")
        self._disconnect_btn.setEnabled(False)
        self._disconnect_btn.clicked.connect(self._on_disconnect)
        top.addWidget(self._disconnect_btn)

        self._load_btn = QPushButton("📂 Завантажити")
        self._load_btn.setToolTip("Завантажити раніше збережений запис  [Ctrl+O]")
        self._load_btn.clicked.connect(self._on_load_file)
        top.addWidget(self._load_btn)

        self._export_btn = QPushButton("💾 Експорт")
        self._export_btn.setToolTip("Експорт у WITRN CSV  [Ctrl+S]\nShift+Ctrl+S — стандартний CSV\nCtrl+J — JSON")
        self._export_btn.clicked.connect(lambda: self._on_export("witrn_csv"))
        top.addWidget(self._export_btn)

        self._report_btn = QPushButton("📝 Звіт")
        self._report_btn.setToolTip("Згенерувати звіт аналізу  [Ctrl+R]")
        self._report_btn.clicked.connect(self._on_generate_report)
        top.addWidget(self._report_btn)

        top.addStretch()

        self._cursor_label = QLabel("")
        self._cursor_label.setStyleSheet("color: #00d2ff; font-family: monospace; font-size: 12px;")
        top.addWidget(self._cursor_label)

        self._status_label = QLabel("● Не підключено")
        self._status_label.setStyleSheet("color: #e94560; font-weight: bold;")
        top.addWidget(self._status_label)

        root.addLayout(top)

        # Main splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # LEFT: controls
        left_widget = QWidget()
        left_lay = QVBoxLayout(left_widget)
        left_lay.setContentsMargins(0, 0, 0, 0)
        left_lay.setSpacing(6)

        # Metric cards
        cards_grid = QGridLayout()
        cards_grid.setSpacing(6)
        self._card_v = MetricCard("Напруга VBUS", "В", "#00d2ff", ".4f")
        self._card_i = MetricCard("Струм IBUS", "А", "#00e676", "+.4f")
        self._card_p = MetricCard("Потужність", "Вт", "#ffea00", ".4f")
        self._card_r = MetricCard("Опір", "Ом", "#e040fb", ".2f")
        self._card_t = MetricCard("Температура", "°C", "#ff5252", ".1f")
        self._card_ah = MetricCard("Ємність", "Ah", "#448aff", ".4f")
        cards_grid.addWidget(self._card_v, 0, 0)
        cards_grid.addWidget(self._card_i, 0, 1)
        cards_grid.addWidget(self._card_p, 1, 0)
        cards_grid.addWidget(self._card_r, 1, 1)
        cards_grid.addWidget(self._card_t, 2, 0)
        cards_grid.addWidget(self._card_ah, 2, 1)
        left_lay.addLayout(cards_grid)

        # Analysis controls
        analysis_group = QGroupBox("🔍 Аналіз")
        an_lay = QGridLayout(analysis_group)
        an_lay.addWidget(QLabel("Ковзне середнє (вікно):"), 0, 0)
        self._ma_spin = QSpinBox()
        self._ma_spin.setRange(2, 500)
        self._ma_spin.setValue(10)
        self._ma_spin.setToolTip("Розмір вікна ковзного середнього  [M — увімкн/вимк]")
        self._ma_spin.valueChanged.connect(self._on_ma_changed)
        an_lay.addWidget(self._ma_spin, 0, 1)

        an_lay.addWidget(QLabel("Чутливість піків:"), 1, 0)
        self._peak_sens = QDoubleSpinBox()
        self._peak_sens.setRange(0.001, 10.0)
        self._peak_sens.setValue(0.05)
        self._peak_sens.setDecimals(3)
        self._peak_sens.setToolTip("Мінімальна провина піку  [P — увімкн/вимк]")
        self._peak_sens.valueChanged.connect(lambda _: self._toggle_peaks(self._act_peaks.isChecked()))
        an_lay.addWidget(self._peak_sens, 1, 1)

        self._apply_analysis_btn = QPushButton("🔄 Оновити аналіз")
        self._apply_analysis_btn.setToolTip("Перебудувати графіки з поточними налаштуваннями  [Enter]")
        self._apply_analysis_btn.clicked.connect(self._redraw_all)
        an_lay.addWidget(self._apply_analysis_btn, 2, 0, 1, 2)
        left_lay.addWidget(analysis_group)

        # Record controls
        rec_group = QGroupBox("⏺ Запис")
        rec_lay = QGridLayout(rec_group)
        rec_lay.addWidget(QLabel("Частота:"), 0, 0)
        self._rate_combo = QComboBox()
        self._rate_combo.addItems(["Макс", "1 Гц", "10 Гц", "50 Гц", "100 Гц"])
        self._rate_combo.setCurrentIndex(2)
        rec_lay.addWidget(self._rate_combo, 0, 1)
        self._autostop_check = QCheckBox("Автозупинка")
        rec_lay.addWidget(self._autostop_check, 0, 2)
        rec_lay.addWidget(QLabel("Поріг:"), 1, 0)
        self._threshold_spin = QDoubleSpinBox()
        self._threshold_spin.setRange(0.001, 100.0)
        self._threshold_spin.setValue(0.05)
        self._threshold_spin.setSuffix(" A/Вт")
        rec_lay.addWidget(self._threshold_spin, 1, 1)
        self._duration_spin = QDoubleSpinBox()
        self._duration_spin.setRange(0.5, 3600.0)
        self._duration_spin.setValue(10.0)
        self._duration_spin.setSuffix(" с")
        rec_lay.addWidget(QLabel("Трив.:"), 2, 0)
        rec_lay.addWidget(self._duration_spin, 2, 1)
        btn_row = QHBoxLayout()
        self._rec_btn = QPushButton("🔴 Почати запис")
        self._rec_btn.setObjectName("recBtn")
        self._rec_btn.setEnabled(False)
        self._rec_btn.setToolTip("Почати запис у SQLite  [F9]")
        self._rec_btn.clicked.connect(self._on_record_start)
        btn_row.addWidget(self._rec_btn)
        self._stop_btn = QPushButton("⏹ Стоп")
        self._stop_btn.setObjectName("stopBtn")
        self._stop_btn.setEnabled(False)
        self._stop_btn.setToolTip("Зупинити запис  [F9]")
        self._stop_btn.clicked.connect(self._on_record_stop)
        btn_row.addWidget(self._stop_btn)
        rec_lay.addLayout(btn_row, 3, 0, 1, 3)
        self._rec_status = QLabel("")
        self._rec_status.setStyleSheet("color: #ffea00;")
        rec_lay.addWidget(self._rec_status, 4, 0, 1, 3)
        left_lay.addWidget(rec_group)

        # Stats
        stats_group = QGroupBox("📊 Статистика")
        stats_lay = QGridLayout(stats_group)
        self._stat_count = QLabel("0")
        self._stat_dur = QLabel("0.0 с")
        self._stat_mah = QLabel("0.00 mAh")
        self._stat_mwh = QLabel("0.00 mWh")
        self._stat_vmin = QLabel("—")
        self._stat_vmax = QLabel("—")
        self._stat_imin = QLabel("—")
        self._stat_imax = QLabel("—")
        self._stat_pp = QLabel("—")
        self._stat_peaks_count = QLabel("0")
        for row, (lbl, val) in enumerate([
            ("Точок:", self._stat_count),
            ("Тривалість:", self._stat_dur),
            ("Ємність:", self._stat_mah),
            ("Енергія:", self._stat_mwh),
            ("V min/max:", self._stat_vmin),
            ("I min/max:", self._stat_imin),
            ("Vpp/Ipp:", self._stat_pp),
            ("Піків:", self._stat_peaks_count),
        ]):
            stats_lay.addWidget(QLabel(lbl), row, 0)
            stats_lay.addWidget(val, row, 1)
        left_lay.addWidget(stats_group)

        # Loaded file info
        self._loaded_info = QLabel("Файл: —")
        self._loaded_info.setStyleSheet("color: #888; font-size: 11px;")
        self._loaded_info.setWordWrap(True)
        left_lay.addWidget(self._loaded_info)

        left_lay.addStretch()
        splitter.addWidget(left_widget)

        # RIGHT: tabs (plots / data table / report)
        right_tabs = QTabWidget()

        # Tab 1: plots
        plots_widget = QWidget()
        plots_lay = QVBoxLayout(plots_widget)
        plots_lay.setContentsMargins(0, 0, 0, 0)
        pg.setConfigOptions(antialias=True, background="#1a1a2e", foreground="#e0e0e0")

        self._plot_v = pg.PlotWidget(title="Напруга (V)")
        self._plot_v.setLabel("left", "V")
        self._plot_v.showGrid(x=True, y=True, alpha=0.2)
        self._curve_v = self._plot_v.plot(pen=pg.mkPen("#00d2ff", width=1.5))
        self._curve_v_ma = self._plot_v.plot(pen=pg.mkPen("#00d2ff", width=2.5, style=Qt.PenStyle.DashLine))
        self._scatter_v = pg.ScatterPlotItem(size=8, brush=pg.mkBrush(255, 255, 255, 180), pen=None)
        self._plot_v.addItem(self._scatter_v)
        self._ref_curve_v = self._plot_v.plot(pen=pg.mkPen("#555555", width=1.0, style=Qt.PenStyle.DotLine))
        plots_lay.addWidget(self._plot_v)

        self._plot_i = pg.PlotWidget(title="Струм (A)")
        self._plot_i.setLabel("left", "A")
        self._plot_i.showGrid(x=True, y=True, alpha=0.2)
        self._curve_i = self._plot_i.plot(pen=pg.mkPen("#00e676", width=1.5))
        self._curve_i_ma = self._plot_i.plot(pen=pg.mkPen("#00e676", width=2.5, style=Qt.PenStyle.DashLine))
        self._scatter_i = pg.ScatterPlotItem(size=8, brush=pg.mkBrush(255, 255, 255, 180), pen=None)
        self._plot_i.addItem(self._scatter_i)
        self._ref_curve_i = self._plot_i.plot(pen=pg.mkPen("#555555", width=1.0, style=Qt.PenStyle.DotLine))
        plots_lay.addWidget(self._plot_i)

        self._plot_p = pg.PlotWidget(title="Потужність (W)")
        self._plot_p.setLabel("left", "W")
        self._plot_p.setLabel("bottom", "t, с")
        self._plot_p.showGrid(x=True, y=True, alpha=0.2)
        self._curve_p = self._plot_p.plot(pen=pg.mkPen("#ffea00", width=1.5))
        self._curve_p_ma = self._plot_p.plot(pen=pg.mkPen("#ffea00", width=2.5, style=Qt.PenStyle.DashLine))
        self._scatter_p = pg.ScatterPlotItem(size=8, brush=pg.mkBrush(255, 255, 255, 180), pen=None)
        self._plot_p.addItem(self._scatter_p)
        self._ref_curve_p = self._plot_p.plot(pen=pg.mkPen("#555555", width=1.0, style=Qt.PenStyle.DotLine))
        plots_lay.addWidget(self._plot_p)

        # Sync X-axis (time) across all three plots: zoom/pan on any = all follow
        # IMPORTANT: pyqtgraph's link maps ranges via screen geometry — if left-axis
        # widths differ (auto-sized by tick labels), ranges shift by a few px per plot.
        # Fix: pin identical axis widths so ViewBoxes share exact geometry.
        for plot in (self._plot_v, self._plot_i, self._plot_p):
            plot.plotItem.getAxis("left").setWidth(64)
        self._plot_i.setXLink(self._plot_v)
        self._plot_p.setXLink(self._plot_v)
        # Master (V) auto-ranges X to data; followers mirror master exactly
        # (X auto-range disabled on followers, otherwise each applies its own
        #  padding and ranges diverge by a few percent)
        for plot in (self._plot_i, self._plot_p):
            plot.plotItem.vb.enableAutoRange(axis=pg.ViewBox.XAxis, enable=False)
        # Only bottom plot shows time labels
        for plot in (self._plot_v, self._plot_i):
            plot.plotItem.getAxis("bottom").setVisible(False)

        # Crosshair lines
        self._vline = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen("#ffffff88", width=1))
        self._hline = pg.InfiniteLine(angle=0, movable=False, pen=pg.mkPen("#ffffff88", width=1))
        self._plot_v.addItem(self._vline, ignoreBounds=True)
        self._plot_i.addItem(self._vline, ignoreBounds=True)
        self._plot_p.addItem(self._vline, ignoreBounds=True)
        self._plot_v.addItem(self._hline, ignoreBounds=True)

        for plot in (self._plot_v, self._plot_i, self._plot_p):
            plot.setBackground("#13132b")
            plot.getPlotItem().setMenuEnabled(True)
            plot.scene().sigMouseMoved.connect(self._on_mouse_moved)

        right_tabs.addTab(plots_widget, "📈 Графіки")

        # Tab 2: data table
        self._data_table = QTableWidget()
        self._data_table.setColumnCount(8)
        self._data_table.setHorizontalHeaderLabels(
            ["t (с)", "V (В)", "I (А)", "P (Вт)", "R (Ом)", "Tвн (°C)", "Tзов (°C)", "Ah"]
        )
        right_tabs.addTab(self._data_table, "📋 Дані")

        # Tab 3: report
        self._report_text = QTextEdit()
        self._report_text.setReadOnly(True)
        right_tabs.addTab(self._report_text, "📝 Звіт")

        splitter.addWidget(right_tabs)
        splitter.setSizes([380, 820])
        root.addWidget(splitter)

    def _init_plots(self):
        pass

    # ── Mouse / crosshair ───────────────────────────────────────────────────
    def _on_mouse_moved(self, pos):
        if not self._show_cursor:
            return
        mouse_point = self._plot_v.plotItem.vb.mapSceneToView(pos)
        x = mouse_point.x()
        self._vline.setPos(x)

        # Find nearest sample
        if self._buf_t:
            ts = list(self._buf_t)
            idx = min(range(len(ts)), key=lambda i: abs(ts[i] - x))
            if abs(ts[idx] - x) < 0.5:
                vs = list(self._buf_v)
                is_ = list(self._buf_i)
                ps = list(self._buf_p)
                self._hline.setPos(vs[idx])
                self._cursor_label.setText(
                    f"t={ts[idx]:.2f}с  V={vs[idx]:.4f}  I={is_[idx]:+.4f}  P={ps[idx]:.4f}"
                )
                return
        self._cursor_label.setText("")

    # ── View toggles ────────────────────────────────────────────────────────
    def _toggle_cursor(self, checked: bool):
        self._show_cursor = checked
        self._vline.setVisible(checked)
        self._hline.setVisible(checked)
        if not checked:
            self._cursor_label.setText("")

    def _toggle_ma(self, checked: bool):
        w = self._ma_spin.value()
        self._ma_window = w
        for curve, buf in ((self._curve_v_ma, self._buf_v), (self._curve_i_ma, self._buf_i), (self._curve_p_ma, self._buf_p)):
            if checked and len(buf) >= 2:
                ts = list(self._buf_t)
                ma = _moving_average(list(buf), w)
                curve.setData(ts, ma)
            else:
                curve.setData([], [])

    def _on_ma_changed(self, val: int):
        self._ma_window = val
        if self._act_ma.isChecked():
            self._toggle_ma(True)

    def _toggle_peaks(self, checked: bool):
        self._show_peaks = checked
        sens = self._peak_sens.value()
        # Compute peaks on power curve
        if checked and len(self._buf_p) >= 3:
            ts = list(self._buf_t)
            ps = list(self._buf_p)
            peaks = _detect_peaks(ts, ps, min_prominence=sens)
            if peaks:
                px, py = zip(*peaks)
                self._scatter_p.setData(list(px), list(py))
            else:
                self._scatter_p.setData([], [])
            self._stat_peaks_count.setText(str(len(peaks)))
        else:
            self._scatter_p.setData([], [])
            self._stat_peaks_count.setText("0")

    def _reset_zoom(self):
        for plot in (self._plot_v, self._plot_i, self._plot_p):
            plot.enableAutoRange()

    # ── Connection ──────────────────────────────────────────────────────────
    def _on_connect(self):
        if self._thread and self._thread.isRunning():
            return
        sim = self._mode_combo.currentIndex() == 0
        self._thread = DeviceThread(simulator=sim)
        self._thread.sample_ready.connect(self._on_sample)
        self._thread.error.connect(self._on_error)
        self._thread.connected.connect(self._on_connected)
        self._thread.start()
        self._status_label.setText("⏳ Підключення…")
        self._status_label.setStyleSheet("color: #ffea00; font-weight: bold;")

    def _on_connected(self, info: dict):
        self._status_label.setText(f"● {info.get('name', '?')}")
        self._status_label.setStyleSheet("color: #00e676; font-weight: bold;")
        self._connect_btn.setEnabled(False)
        self._disconnect_btn.setEnabled(True)
        self._rec_btn.setEnabled(True)

    def _on_disconnect(self):
        if self._thread:
            self._thread.stop()
            self._thread = None
        if self._recorder and self._recorder.is_recording:
            self._on_record_stop()
        self._status_label.setText("● Не підключено")
        self._status_label.setStyleSheet("color: #e94560; font-weight: bold;")
        self._connect_btn.setEnabled(True)
        self._disconnect_btn.setEnabled(False)
        self._rec_btn.setEnabled(False)

    def _on_error(self, msg: str):
        self._status_label.setText(f"❌ {msg[:60]}")
        self._status_label.setStyleSheet("color: #e94560; font-weight: bold;")

    # ── Sample handling ─────────────────────────────────────────────────────
    def _on_sample(self, sample: Sample):
        self._last_sample = sample
        self._buf_t.append(sample.time)
        self._buf_v.append(sample.voltage)
        self._buf_i.append(sample.current)
        self._buf_p.append(sample.power)
        self._all_samples.append(sample)

        if self._recorder and self._recorder.is_recording:
            auto = self._recorder.feed(sample)
            if auto:
                self._on_record_stop()
                QMessageBox.information(self, "Автозупинка", "Спрацювала умова автозупинки.")

    # ── Load / import ───────────────────────────────────────────────────────
    def _on_load_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Завантажити запис", "recordings",
            "SQLite (*.sqlite);;Усі файли (*)"
        )
        if not path:
            return
        try:
            samples = list(read_sqlite_samples(Path(path)))
            self._loaded_samples = samples
            self._loaded_name = Path(path).name
            self._loaded_info.setText(f"Файл: {self._loaded_name}  ({len(samples)} точок)")
            self._redraw_all()
            self._fill_table(samples)
            QMessageBox.information(self, "OK", f"Завантажено {len(samples)} точок з {self._loaded_name}")
        except Exception as exc:
            QMessageBox.critical(self, "Помилка", f"Не вдалося завантажити:\n{exc}")

    def _on_load_csv(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Завантажити CSV", "recordings",
            "CSV (*.csv);;Усі файли (*)"
        )
        if not path:
            return
        try:
            samples = import_official_csv(Path(path))
            self._loaded_samples = samples
            self._loaded_name = Path(path).name
            self._loaded_info.setText(f"Файл: {self._loaded_name}  ({len(samples)} точок)")
            self._redraw_all()
            self._fill_table(samples)
            QMessageBox.information(self, "OK", f"Завантажено {len(samples)} точок з {self._loaded_name}")
        except Exception as exc:
            QMessageBox.critical(self, "Помилка", f"Не вдалося завантажити CSV:\n{exc}")

    def _on_load_reference(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Завантажити референсну сесію", "recordings",
            "SQLite (*.sqlite);;CSV (*.csv);;Усі файли (*)"
        )
        if not path:
            return
        try:
            p = Path(path)
            if p.suffix.lower() == ".sqlite":
                samples = list(read_sqlite_samples(p))
            else:
                samples = import_official_csv(p)
            self._ref_samples = samples
            self._ref_name = p.name
            self._redraw_all()
            QMessageBox.information(self, "OK", f"Референс: {p.name} ({len(samples)} точок)")
        except Exception as exc:
            QMessageBox.critical(self, "Помилка", f"Не вдалося завантажити референс:\n{exc}")

    def _on_clear_reference(self):
        self._ref_samples = []
        self._ref_name = ""
        self._ref_curve_v.setData([], [])
        self._ref_curve_i.setData([], [])
        self._ref_curve_p.setData([], [])

    # ── Export ──────────────────────────────────────────────────────────────
    def _on_export(self, fmt: str):
        samples = self._get_active_samples()
        if not samples:
            QMessageBox.warning(self, "Порожньо", "Немає даних для експорту.")
            return
        ext_map = {"witrn_csv": "WITRN CSV (*.csv)", "standard_csv": "CSV (*.csv)", "json": "JSON (*.json)"}
        path, _ = QFileDialog.getSaveFileName(
            self, "Експорт", f"export_{time.strftime('%Y%m%d_%H%M%S')}",
            ext_map.get(fmt, "Усі файли (*)")
        )
        if not path:
            return
        try:
            p = Path(path)
            if fmt == "witrn_csv":
                export_official_csv(samples, p)
            elif fmt == "standard_csv":
                export_standard_csv(samples, p)
            elif fmt == "json":
                export_json(samples, p)
            QMessageBox.information(self, "OK", f"Експортовано: {p.name}")
        except Exception as exc:
            QMessageBox.critical(self, "Помилка", f"Експорт не вдався:\n{exc}")

    def _get_active_samples(self) -> list[Sample]:
        if self._loaded_samples:
            return self._loaded_samples
        return self._all_samples[-5000:]

    # ── Vector SVG export of all three plots ────────────────────────────────
    def _on_export_svg(self):
        samples = self._get_active_samples()
        if len(samples) < 2:
            QMessageBox.warning(self, "Порожньо", "Немає даних для експорту графіків.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Векторний експорт графіків", f"graphs_{time.strftime('%Y%m%d_%H%M%S')}.svg",
            "SVG — вектор (*.svg)"
        )
        if not path:
            return
        try:
            self._export_svg(Path(path), samples)
            QMessageBox.information(self, "OK", f"Векторний SVG збережено:\n{path}")
        except Exception as exc:
            QMessageBox.critical(self, "Помилка", f"Експорт SVG не вдався:\n{exc}")

    def _export_svg(self, path: Path, samples: list[Sample]):
        from pyqtgraph.exporters import SVGExporter

        from .svgfix import patch_pyqtgraph_svg_export

        # Qt 6.11 path data crashes stock pyqtgraph SVG exporter (Z/H/V tokens)
        patch_pyqtgraph_svg_export()

        ts = [s.time for s in samples]
        vs = [s.voltage for s in samples]
        is_ = [s.current for s in samples]
        ps = [s.power for s in samples]
        ref_ts = [s.time for s in self._ref_samples] if self._ref_samples else None
        ref_vs = [s.voltage for s in self._ref_samples] if self._ref_samples else None
        ref_is = [s.current for s in self._ref_samples] if self._ref_samples else None
        ref_ps = [s.power for s in self._ref_samples] if self._ref_samples else None
        show_ma = self._act_ma.isChecked()
        ma_w = self._ma_window

        glw = pg.GraphicsLayoutWidget()
        glw.setBackground("w")
        glw.resize(1100, 760)

        specs = [
            ("Напруга (V)", "V", "#00a0c0", vs, ref_vs),
            ("Струм (A)", "A", "#00a855", is_, ref_is),
            ("Потужність (W)", "W", "#d0a000", ps, ref_ps),
        ]
        created_plots = []
        for idx, (title, unit, color, vals, ref_vals) in enumerate(specs):
            p = glw.addPlot(title=title, row=idx, col=0)
            p.setLabel("left", unit)
            p.showGrid(x=True, y=True, alpha=0.25)
            if idx == len(specs) - 1:
                p.setLabel("bottom", "t, с")
            p.plot(ts, vals, pen=pg.mkPen(color, width=1.5), name=title)
            if show_ma and len(vals) >= 2:
                p.plot(ts, _moving_average(vals, ma_w),
                       pen=pg.mkPen(color, width=2.2, style=Qt.PenStyle.DashLine))
            if ref_ts:
                p.plot(ref_ts, ref_vals,
                       pen=pg.mkPen("#909090", width=1.2, style=Qt.PenStyle.DotLine),
                       name="референс")
            # Peak markers on power plot (vector scatter)
            if idx == 2 and self._act_peaks.isChecked():
                peaks = _detect_peaks(ts, ps, min_prominence=self._peak_sens.value())
                if peaks:
                    px, py = zip(*peaks)
                    p.plot(list(px), list(py), pen=None,
                           symbol="o", symbolSize=9,
                           symbolBrush=pg.mkBrush(230, 40, 60, 200),
                           symbolPen=pg.mkPen("#800010"))
            created_plots.append(p)

        # Time-axis sync inside the export too
        created_plots[1].setXLink(created_plots[0])
        created_plots[2].setXLink(created_plots[0])

        # Force layout geometry before exporting
        glw.show()
        app = QApplication.instance()
        for _ in range(3):
            app.processEvents()

        exporter = SVGExporter(glw.scene())
        exporter.export(str(path))
        glw.hide()
        glw.deleteLater()

    # ── Report generation ───────────────────────────────────────────────────
    def _on_generate_report(self):
        samples = self._get_active_samples()
        if len(samples) < 2:
            QMessageBox.warning(self, "Замало даних", "Потрібно щонайменше 2 точки.")
            return
        report = build_report(
            samples,
            ref_samples=self._ref_samples or None,
            source=self._loaded_name if self._loaded_name else "жива сесія",
            ref_name=self._ref_name or "",
            ma_window=self._ma_window,
            peak_sens=self._peak_sens.value(),
        )

        self._report_text.setPlainText(report)
        # Switch to report tab
        parent = self._report_text.parent()
        while parent and not isinstance(parent, QTabWidget):
            parent = parent.parent()
        if isinstance(parent, QTabWidget):
            parent.setCurrentWidget(self._report_text)

    def _detect_phases(self, ts: list[float], ps: list[float]) -> list[tuple[str, float, float, float]]:
        """Simple 3-phase charge detection: ramp-up, steady, taper."""
        return detect_phases(ts, ps)

    # ── Redraw everything ───────────────────────────────────────────────────
    def _redraw_all(self):
        """Redraw plots from loaded samples (if any) or live buffers."""
        if self._loaded_samples:
            ts = [s.time for s in self._loaded_samples]
            vs = [s.voltage for s in self._loaded_samples]
            is_ = [s.current for s in self._loaded_samples]
            ps = [s.power for s in self._loaded_samples]
        elif self._buf_t:
            ts = list(self._buf_t)
            vs = list(self._buf_v)
            is_ = list(self._buf_i)
            ps = list(self._buf_p)
        else:
            return

        self._curve_v.setData(ts, vs)
        self._curve_i.setData(ts, is_)
        self._curve_p.setData(ts, ps)

        # MA overlay
        if self._act_ma.isChecked() and len(vs) >= 2:
            self._curve_v_ma.setData(ts, _moving_average(vs, self._ma_window))
            self._curve_i_ma.setData(ts, _moving_average(is_, self._ma_window))
            self._curve_p_ma.setData(ts, _moving_average(ps, self._ma_window))
        else:
            self._curve_v_ma.setData([], [])
            self._curve_i_ma.setData([], [])
            self._curve_p_ma.setData([], [])

        # Peaks
        if self._act_peaks.isChecked():
            peaks = _detect_peaks(ts, ps, min_prominence=self._peak_sens.value())
            if peaks:
                px, py = zip(*peaks)
                self._scatter_p.setData(list(px), list(py))
            else:
                self._scatter_p.setData([], [])
            self._stat_peaks_count.setText(str(len(peaks)))

        # Reference overlay
        if self._ref_samples:
            rts = [s.time for s in self._ref_samples]
            self._ref_curve_v.setData(rts, [s.voltage for s in self._ref_samples])
            self._ref_curve_i.setData(rts, [s.current for s in self._ref_samples])
            self._ref_curve_p.setData(rts, [s.power for s in self._ref_samples])
        else:
            self._ref_curve_v.setData([], [])
            self._ref_curve_i.setData([], [])
            self._ref_curve_p.setData([], [])

    # ── Data table ──────────────────────────────────────────────────────────
    def _fill_table(self, samples: list[Sample], max_rows: int = 2000):
        self._data_table.setRowCount(0)
        display = samples[:max_rows]
        self._data_table.setRowCount(len(display))
        for row, s in enumerate(display):
            for col, val in enumerate([
                f"{s.time:.3f}",
                f"{s.voltage:.4f}" if s.voltage is not None else "",
                f"{s.current:+.4f}" if s.current is not None else "",
                f"{s.power:.4f}" if s.power is not None else "",
                f"{s.resistance:.2f}" if s.resistance is not None else "",
                f"{s.temp_in:.1f}" if s.temp_in is not None else "",
                f"{s.temp_out:.1f}" if s.temp_out is not None else "",
                f"{s.ah:.5f}" if s.ah is not None else "",
            ]):
                item = QTableWidgetItem(val)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self._data_table.setItem(row, col, item)

    # ── UI refresh ──────────────────────────────────────────────────────────
    def _refresh_ui(self):
        s = self._last_sample
        if not s:
            return

        self._card_v.set_value(s.voltage)
        self._card_i.set_value(s.current)
        self._card_p.set_value(s.power)
        self._card_r.set_value(s.resistance)
        ti = f"{s.temp_in:.1f}" if s.temp_in is not None else "—"
        to = f"{s.temp_out:.1f}" if s.temp_out is not None else "—"
        self._card_t.set_value(s.temp_in, f"зовн: {to}°C")
        self._card_ah.set_value(s.ah, f"Wh:{s.wh or 0:.4f} D+:{s.dp or 0:.2f} D-:{s.dn or 0:.2f}")

        # Live curve update (only if no loaded file is shown)
        if not self._loaded_samples:
            n = len(self._buf_t)
            window = min(n, 1500)
            xs = list(self._buf_t)[-window:]
            self._curve_v.setData(xs, list(self._buf_v)[-window:])
            self._curve_i.setData(xs, list(self._buf_i)[-window:])
            self._curve_p.setData(xs, list(self._buf_p)[-window:])

            if self._act_ma.isChecked():
                self._curve_v_ma.setData(xs, _moving_average(list(self._buf_v)[-window:], self._ma_window))
                self._curve_i_ma.setData(xs, _moving_average(list(self._buf_i)[-window:], self._ma_window))
                self._curve_p_ma.setData(xs, _moving_average(list(self._buf_p)[-window:], self._ma_window))

    def _refresh_stats(self):
        samples = self._loaded_samples if self._loaded_samples else self._all_samples[-5000:]
        if len(samples) < 2:
            return
        stats = calculate_statistics(samples)
        ch = stats.get("channels", {})
        en = stats.get("energy", {})

        self._stat_count.setText(str(stats.get("count", 0)))
        self._stat_dur.setText(f"{stats.get('duration_sec', 0):.1f} с")
        self._stat_mah.setText(f"{en.get('mah_net', 0):.2f} mAh")
        self._stat_mwh.setText(f"{en.get('mwh_net', 0):.2f} mWh")

        vch = ch.get("voltage", {})
        ich = ch.get("current", {})
        self._stat_vmin.setText(f"{vch.get('min', 0):.3f} / {vch.get('max', 0):.3f} В")
        self._stat_imin.setText(f"{ich.get('min', 0):.3f} / {ich.get('max', 0):.3f} А")

        vpp = (vch.get("max", 0) or 0) - (vch.get("min", 0) or 0)
        ipp = (ich.get("max", 0) or 0) - (ich.get("min", 0) or 0)
        self._stat_pp.setText(f"{vpp:.4f} В / {ipp:.4f} А")

    # ── Recording ───────────────────────────────────────────────────────────
    def _on_record_start(self):
        rate_map = [0, 1, 10, 50, 100]
        rate = rate_map[self._rate_combo.currentIndex()]
        rule = AutoStopRule(
            enabled=self._autostop_check.isChecked(),
            kind="current",
            threshold=self._threshold_spin.value(),
            duration=self._duration_spin.value(),
        )
        out_dir = Path("recordings")
        out_dir.mkdir(exist_ok=True)
        self._recorder = Recorder(out_dir)
        ts = time.strftime("%Y%m%d_%H%M%S")
        path = self._recorder.start(session_name=f"session_{ts}", rate=rate, auto_rule=rule)
        self._rec_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._rec_status.setText(f"⏺ Запис: {path.name}")

    def _on_record_stop(self):
        if self._recorder and self._recorder.is_recording:
            path = self._recorder.stop()
            self._rec_status.setText(f"✓ Збережено: {path.name}")
        self._rec_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)

    # ── Record toggle (F9) ──────────────────────────────────────────────────
    def _on_record_toggle(self):
        if self._recorder and self._recorder.is_recording:
            self._on_record_stop()
        elif self._rec_btn.isEnabled():
            self._on_record_start()

    # ── Clear live data ─────────────────────────────────────────────────────
    def _on_clear_live(self):
        self._buf_t.clear()
        self._buf_v.clear()
        self._buf_i.clear()
        self._buf_p.clear()
        self._all_samples.clear()
        self._loaded_samples = []
        self._loaded_name = ""
        self._last_sample = None
        self._loaded_info.setText("Файл: —")
        self._curve_v.setData([], [])
        self._curve_i.setData([], [])
        self._curve_p.setData([], [])
        self._curve_v_ma.setData([], [])
        self._curve_i_ma.setData([], [])
        self._curve_p_ma.setData([], [])
        self._scatter_p.setData([], [])
        self._data_table.setRowCount(0)
        self._report_text.clear()

    # ── Shortcuts help dialog ───────────────────────────────────────────────
    def _show_shortcuts(self):
        QMessageBox.information(self, "Гарячі клавіші", """\
⌨  ГАРЯЧІ КЛАВІШІ WITRN K2

— Зв'язок —
  F5            Підключити
  Esc           Відключити

— Файл —
  Ctrl+O        Завантажити запис (SQLite)
  Ctrl+Shift+O  Завантажити CSV
  Ctrl+S        Експорт WITRN CSV
  Ctrl+Shift+S  Експорт стандартний CSV
  Ctrl+J        Експорт JSON
  Ctrl+Shift+V  Експорт графіків SVG (вектор)
  Ctrl+R        Згенерувати звіт
  Ctrl+Q        Вихід

— Запис —
  F9            Почати / зупинити запис

— Вигляд —
  C             Курсор (crosshair) вкл/викл
  M             Ковзне середнє вкл/викл
  P             Детекція піків вкл/викл
  Ctrl+0        Скинути масштаб графіків
  Ctrl+Delete   Очистити живі дані

— Порівняння —
  Ctrl+Shift+R  Завантажити референсну сесію
  Ctrl+Shift+D  Очистити референс

— Інше —
  F1            Ця довідка""")

    # ── Close ───────────────────────────────────────────────────────────────
    def closeEvent(self, event):
        if self._thread:
            self._thread.stop()
        if self._recorder and self._recorder.is_recording:
            self._recorder.stop()
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
