"""Vector SVG chart export shared by the GUI and the web server.

Renders the three stacked plots (V / I / P) with optional moving-average
overlay, reference session overlay and peak markers into a single SVG file
using pyqtgraph, with a Qt 6 compatibility patch (see ``witrn_k2.svgfix``).
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from .analytics import detect_peaks, moving_average
from .telemetry import Sample


def export_samples_svg(
    path: Path,
    samples: List[Sample],
    ref_samples: Optional[List[Sample]] = None,
    show_ma: bool = False,
    ma_window: int = 10,
    show_peaks: bool = False,
    peak_sens: float = 0.05,
    width: int = 1100,
    height: int = 760,
) -> Path:
    """Export V/I/P plots of ``samples`` as one vector SVG file."""
    import pyqtgraph as pg
    from pyqtgraph.exporters import SVGExporter

    from ..svgfix import patch_pyqtgraph_svg_export

    # Qt 6.11 path data crashes stock pyqtgraph SVG exporter (Z/H/V tokens)
    patch_pyqtgraph_svg_export()

    ts = [s.time for s in samples]
    vs = [s.voltage for s in samples]
    is_ = [s.current for s in samples]
    ps = [s.power for s in samples]
    ref_ts = [s.time for s in ref_samples] if ref_samples else None
    ref_vs = [s.voltage for s in ref_samples] if ref_samples else None
    ref_is = [s.current for s in ref_samples] if ref_samples else None
    ref_ps = [s.power for s in ref_samples] if ref_samples else None

    from PyQt6.QtCore import Qt

    glw = pg.GraphicsLayoutWidget()
    glw.setBackground("w")
    glw.resize(width, height)

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
            p.plot(
                ts,
                moving_average(vals, ma_window),
                pen=pg.mkPen(color, width=2.2, style=Qt.PenStyle.DashLine),
            )
        if ref_ts:
            p.plot(
                ref_ts,
                ref_vals,
                pen=pg.mkPen("#909090", width=1.2, style=Qt.PenStyle.DotLine),
                name="референс",
            )
        if idx == 2 and show_peaks:
            peaks = detect_peaks(ts, ps, min_prominence=peak_sens)
            if peaks:
                px, py = zip(*peaks)
                p.plot(
                    list(px),
                    list(py),
                    pen=None,
                    symbol="o",
                    symbolSize=9,
                    symbolBrush=pg.mkBrush(230, 40, 60, 200),
                    symbolPen=pg.mkPen("#800010"),
                )
        created_plots.append(p)

    # Time-axis sync inside the export too
    created_plots[1].setXLink(created_plots[0])
    created_plots[2].setXLink(created_plots[0])

    # Force layout geometry before exporting
    glw.show()
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is not None:
        for _ in range(3):
            app.processEvents()

    exporter = SVGExporter(glw.scene())
    exporter.export(str(path))
    glw.hide()
    glw.deleteLater()
    return Path(path)
