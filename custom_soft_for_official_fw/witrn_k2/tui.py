"""Full-screen terminal dashboard for WITRN K2 using rich."""
from __future__ import annotations

import time
from collections import deque
from typing import Optional

from rich.align import Align
from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .core.analytics import calculate_statistics
from .core.telemetry import Sample

_SPARK_CHARS = "▁▂▃▄▅▆▇█"


def _sparkline(data, width: int = 40) -> str:
    if not data:
        return ""
    vals = list(data)
    if len(vals) > width:
        step = len(vals) / width
        sampled = []
        for i in range(width):
            start = int(i * step)
            end = int((i + 1) * step)
            chunk = vals[start:end] if end > start else [vals[start]]
            sampled.append(max(chunk))
        vals = sampled
    lo, hi = min(vals), max(vals)
    if hi == lo:
        return _SPARK_CHARS[0] * len(vals)
    span = hi - lo
    return "".join(_SPARK_CHARS[int((v - lo) / span * (len(_SPARK_CHARS) - 1))] for v in vals)


def _make_spark(data: deque, label: str, color: str) -> Group:
    if not data:
        return Group(Text("—", style="dim"))
    return Group(
        Text(label, style=f"bold {color}"),
        Text(_sparkline(list(data), width=40), style=color),
    )


def _metric_box(title: str, value: str, unit: str, color: str, extra: str = "") -> Panel:
    body = Text()
    body.append(value, style=f"bold {color}")
    body.append(f" {unit}", style="dim")
    if extra:
        body.append(f"\n{extra}", style="dim")
    return Panel(Align.center(body), title=f"[bold]{title}[/]", border_style=color, padding=(0, 1))


def _f(val, spec=".4f", dash="—"):
    return format(val, spec) if val is not None else dash


def _pair(a, b, spec=".2f", sep="/"):
    if a is None and b is None:
        return "—"
    if a is None:
        return f"—{sep}{b:{spec}}"
    if b is None:
        return f"{a:{spec}}{sep}—"
    return f"{a:{spec}}{sep}{b:{spec}}"


def run_dashboard(trans, info: dict, rate: int = 0, record: bool = False,
                  out_path: Optional[str] = None, auto_stop: Optional[dict] = None):
    from .core.recorder import AutoStopRule, Recorder
    from .core.telemetry import decode_report
    from pathlib import Path

    console = Console()

    buf_v: deque = deque(maxlen=200)
    buf_i: deque = deque(maxlen=200)
    buf_p: deque = deque(maxlen=200)
    buf_t: deque = deque(maxlen=200)
    all_samples: list[Sample] = []
    buf_samples: deque = deque(maxlen=3600)

    recorder = None
    if record:
        out = Path(out_path or "recordings/dashboard_capture.sqlite")
        out.parent.mkdir(parents=True, exist_ok=True)
        rule = AutoStopRule(**(auto_stop or {"enabled": False}))
        recorder = Recorder(out.parent)
        db_path = recorder.start(session_name=out.stem, rate=rate, auto_rule=rule)
        console.print(f"[green]● Запис:[/] [cyan]{db_path.name}[/]")

    console.print(f"[dim]Підключено:[/] {info.get('name')}")
    console.print("[dim]Ctrl+C — вихід[/]\n")

    started = time.monotonic()
    sample_count = 0
    fps = 0.0
    last_fps_time = started
    frames_in_fps_window = 0

    def build_layout() -> Layout:
        root = Layout(name="root")
        root.split_column(
            Layout(name="header", size=1),
            Layout(name="main"),
            Layout(name="footer", size=1),
        )
        root["main"].split_row(
            Layout(name="left", ratio=1),
            Layout(name="right", ratio=1),
        )
        root["left"].split_column(
            Layout(name="metrics", ratio=1),
            Layout(name="stats", ratio=1),
        )
        root["right"].split_column(
            Layout(name="charts", ratio=1),
        )
        root["right"]["charts"].split_column(
            Layout(name="chart_v", ratio=1),
            Layout(name="chart_i", ratio=1),
            Layout(name="chart_p", ratio=1),
            Layout(name="chart_t", ratio=1),
        )
        return root

    layout = build_layout()

    def render(sample: Optional[Sample], stats: dict) -> Layout:
        elapsed = time.monotonic() - started
        hh = int(elapsed // 3600)
        mm = int((elapsed % 3600) // 60)
        ss = int(elapsed % 60)
        tstr = f"{hh:02d}:{mm:02d}:{ss:02d}"

        # Header
        rec_badge = ""
        if recorder and recorder.is_recording:
            rec_badge = " [bold red]● REC[/]"
        elif recorder:
            rec_badge = " [dim]○[/]"
        header = Text()
        header.append(" ⚡ WITRN K2", style="bold cyan")
        header.append(f"  ⏱ {tstr}", style="bold yellow")
        header.append(f"  💾 {sample_count}", style="green")
        header.append(f"  ↻ {fps:.0f}fps", style="dim")
        header.append(rec_badge)
        layout["header"].update(Panel(header, border_style="cyan", padding=(0, 0)))

        # Metrics left
        v = sample.voltage if sample else None
        i = sample.current if sample else None
        p = sample.power if sample else None
        r = sample.resistance if sample else None
        dp = sample.dp if sample else None
        dn = sample.dn if sample else None
        ti = sample.temp_in if sample else None
        to = sample.temp_out if sample else None
        ah = sample.ah if sample else None
        wh = sample.wh if sample else None
        rs = sample.record_seconds if sample else None
        up = sample.uptime if sample else None

        grid = Table.grid(expand=True, padding=(0, 1))
        grid.add_row(
            _metric_box("VBUS", _f(v), "V", "cyan",
                        f"Min {stats.get('v_min', 0):.3f} Max {stats.get('v_max', 0):.3f}"),
            _metric_box("IBUS", _f(i, "+.4f"), "A", "green",
                        f"Min {stats.get('i_min', 0):.3f} Max {stats.get('i_max', 0):.3f}"),
        )
        grid.add_row(
            _metric_box("Потужність", _f(p), "W", "yellow",
                        f"Min {stats.get('p_min', 0):.3f} Max {stats.get('p_max', 0):.3f}"),
            _metric_box("Опір", _f(r, ".2f"), "Ω", "magenta",
                        (f"D+{dp:.2f} D-{dn:.2f}" if dp is not None else "")),
        )
        grid.add_row(
            _metric_box("Температура", _pair(ti, to, ".1f"), "°C", "red", "внутр/зовн"),
            _metric_box("Лічильники", _pair(ah, wh, ".4f"), "Ah/Wh", "blue",
                        f"rec{rs or 0}с up{up or 0}с"),
        )
        layout["metrics"].update(grid)

        # Stats
        en = stats.get("energy", {})
        st = Table.grid(expand=True, padding=(0, 1))
        st.add_row(Text("📊 СТАТИСТИКА", style="bold white"))
        st.add_row(Text(f"Точок: {stats.get('count', 0)}  Тривалість: {stats.get('duration', 0):.1f}с", style="dim"))
        st.add_row(Text(
            f"⚡ {en.get('mah_net', 0):.2f} mAh   🔌 {en.get('mwh_net', 0):.2f} mWh",
            style="yellow",
        ))
        layout["stats"].update(Panel(st, border_style="white"))

        # Charts
        layout["chart_v"].update(Panel(_make_spark(buf_v, "Напруга V", "cyan"), border_style="cyan", padding=(0, 1)))
        layout["chart_i"].update(Panel(_make_spark(buf_i, "Струм A", "green"), border_style="green", padding=(0, 1)))
        layout["chart_p"].update(Panel(_make_spark(buf_p, "Потужність W", "yellow"), border_style="yellow", padding=(0, 1)))
        layout["chart_t"].update(Panel(_make_spark(buf_t, "Температура °C", "red"), border_style="red", padding=(0, 1)))

        # Footer
        footer = Text()
        footer.append(" Ctrl+C — вихід ", style="bold white")
        footer.append(f"{' ● запис' if recorder and recorder.is_recording else ''}", style="bold red")
        footer.append(f"  {'симулятор' if info.get('type')=='simulator' else 'USB HID'}", style="dim")
        layout["footer"].update(Panel(footer, border_style="dim", padding=(0, 0)))

        return layout

    def compute_stats(samples: list[Sample]) -> dict:
        if not samples:
            return {"count": 0, "duration": 0.0}
        stats = calculate_statistics(samples)
        ch = stats.get("channels", {})
        en = stats.get("energy", {})
        return {
            "count": stats.get("count", 0),
            "duration": stats.get("duration_sec", 0.0),
            "v_min": ch.get("voltage", {}).get("min", 0.0) or 0.0,
            "v_max": ch.get("voltage", {}).get("max", 0.0) or 0.0,
            "i_min": ch.get("current", {}).get("min", 0.0) or 0.0,
            "i_max": ch.get("current", {}).get("max", 0.0) or 0.0,
            "p_min": ch.get("power", {}).get("min", 0.0) or 0.0,
            "p_max": ch.get("power", {}).get("max", 0.0) or 0.0,
            "energy": en,
        }

    last_stats_update = 0.0
    cached_stats = {"count": 0, "duration": 0.0}
    last_sample: Optional[Sample] = None

    with Live(console=console, refresh_per_second=15, screen=True) as live:
        try:
            while True:
                raw = trans.read(20)
                now = time.monotonic()
                elapsed = now - started

                frames_in_fps_window += 1
                if now - last_fps_time >= 1.0:
                    fps = frames_in_fps_window / (now - last_fps_time)
                    last_fps_time = now
                    frames_in_fps_window = 0

                if raw:
                    try:
                        sample = decode_report(raw, elapsed)
                    except ValueError:
                        sample = None
                    if sample:
                        last_sample = sample
                        sample_count += 1
                        buf_v.append(sample.voltage)
                        buf_i.append(sample.current)
                        buf_p.append(sample.power)
                        if sample.temp_in is not None:
                            buf_t.append(sample.temp_in)
                        buf_samples.append(sample)
                        all_samples.append(sample)

                        if recorder:
                            auto_stopped = recorder.feed(sample)
                            if auto_stopped:
                                break

                display_sample = last_sample if last_sample is not None else (buf_samples[-1] if buf_samples else None)

                if now - last_stats_update >= 1.0:
                    cached_stats = compute_stats(all_samples[-3600:])
                    last_stats_update = now

                live.update(render(display_sample, cached_stats))

        except KeyboardInterrupt:
            pass
        finally:
            if recorder and recorder.is_recording:
                path = recorder.stop()
                console.print(f"[green]✓ Запис збережено:[/] {path}")
            trans.close()
