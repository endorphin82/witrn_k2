"""Analytics, statistics calculation, and piece-wise linear energy integration."""
import math
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Tuple

from .telemetry import Sample

CHANNELS = ("voltage", "current", "power", "temp_in", "temp_out", "dp", "dn")


def direction_area(a: float, b: float, dt: float) -> Tuple[float, float]:
    """Calculate positive and negative areas for a trapezoid, splitting at zero if signs differ."""
    if a >= 0 and b >= 0:
        return (a + b) * dt / 2.0, 0.0
    if a <= 0 and b <= 0:
        return 0.0, -(a + b) * dt / 2.0
    # Zero crossing
    t_zero = dt * abs(a) / (abs(a) + abs(b))
    area_a = abs(a) * t_zero / 2.0
    area_b = abs(b) * (dt - t_zero) / 2.0
    return (area_a, area_b) if a > 0 else (area_b, area_a)


def interpolate_sample(a: Sample, b: Sample, target_time: float) -> Sample:
    """Linearly interpolate sample values at target_time."""
    if b.time == a.time:
        return a
    factor = (target_time - a.time) / (b.time - a.time)
    values = a.dictionary()
    for name in CHANNELS + ("signed_power",):
        va = getattr(a, name)
        vb = getattr(b, name)
        if va is not None and vb is not None:
            values[name] = va + (vb - va) * factor
        else:
            values[name] = None
    values["time"] = target_time
    if values["signed_power"] is not None:
        values["power"] = abs(values["signed_power"])
    return Sample(**values)


def calculate_statistics(
    samples_iter: Iterable[Sample],
    start_time: Optional[float] = None,
    end_time: Optional[float] = None,
    gap_limit: float = 2.0,
) -> Dict:
    """Calculate comprehensive laboratory statistics for a sequence of samples."""
    channel_stats = {
        k: {"min": None, "max": None, "sum_weighted": 0.0, "coverage": 0.0}
        for k in CHANNELS
    }
    resistance_vals = []
    count = 0
    coverage_time = 0.0
    ah_pos = 0.0
    ah_neg = 0.0
    wh_pos = 0.0
    wh_neg = 0.0

    first_time: Optional[float] = None
    last_time: Optional[float] = None
    prev_sample: Optional[Sample] = None

    def observe_point(s: Sample):
        for key in CHANNELS:
            v = getattr(s, key)
            if v is not None and math.isfinite(v):
                st = channel_stats[key]
                st["min"] = min(st["min"], v) if st["min"] is not None else v
                st["max"] = max(st["max"], v) if st["max"] is not None else v
        if s.resistance is not None and math.isfinite(s.resistance):
            resistance_vals.append(s.resistance)

    for s in samples_iter:
        if start_time is not None and s.time < start_time:
            prev_sample = s
            continue
        if end_time is not None and s.time > end_time:
            break

        count += 1
        observe_point(s)
        if first_time is None:
            first_time = s.time
        last_time = s.time

        if prev_sample is not None and prev_sample.segment == s.segment:
            dt = s.time - prev_sample.time
            if 0 < dt <= gap_limit:
                coverage_time += dt
                # Integration for each channel
                for key in CHANNELS:
                    va = getattr(prev_sample, key)
                    vb = getattr(s, key)
                    if va is not None and vb is not None and math.isfinite(va) and math.isfinite(vb):
                        area = (va + vb) * dt / 2.0
                        channel_stats[key]["sum_weighted"] += area
                        channel_stats[key]["coverage"] += dt

                # Capacity (Ah) integration: I (A) * dt (s) / 3600
                i_a, i_b = prev_sample.current, s.current
                pos_i, neg_i = direction_area(i_a, i_b, dt)
                ah_pos += pos_i / 3600.0
                ah_neg += neg_i / 3600.0

                # Energy (Wh) integration: P (W) * dt (s) / 3600
                p_a, p_b = prev_sample.signed_power, s.signed_power
                pos_p, neg_p = direction_area(p_a, p_b, dt)
                wh_pos += pos_p / 3600.0
                wh_neg += neg_p / 3600.0

        prev_sample = s

    # Finalize channel averages and peak-to-peak
    summary_channels = {}
    for key, data in channel_stats.items():
        cov = data["coverage"]
        avg = (data["sum_weighted"] / cov) if cov > 0 else (data["min"] if data["min"] is not None else 0.0)
        v_min = data["min"] if data["min"] is not None else 0.0
        v_max = data["max"] if data["max"] is not None else 0.0
        v_pp = max(0.0, v_max - v_min)
        summary_channels[key] = {
            "min": round(v_min, 4),
            "max": round(v_max, 4),
            "avg": round(avg, 4),
            "vpp": round(v_pp, 4),
        }

    res_stats = {
        "min": round(min(resistance_vals), 2) if resistance_vals else None,
        "max": round(max(resistance_vals), 2) if resistance_vals else None,
        "avg": round(sum(resistance_vals) / len(resistance_vals), 2) if resistance_vals else None,
    }

    total_duration = (last_time - first_time) if (first_time is not None and last_time is not None) else 0.0

    return {
        "count": count,
        "duration_sec": round(total_duration, 3),
        "coverage_sec": round(coverage_time, 3),
        "channels": summary_channels,
        "resistance": res_stats,
        "energy": {
            "mah_forward": round(ah_pos * 1000.0, 2),
            "mah_reverse": round(ah_neg * 1000.0, 2),
            "mah_net": round((ah_pos - ah_neg) * 1000.0, 2),
            "mwh_forward": round(wh_pos * 1000.0, 2),
            "mwh_reverse": round(wh_neg * 1000.0, 2),
            "mwh_net": round((wh_pos - wh_neg) * 1000.0, 2),
        }
    }


# ── Shared analysis helpers (used by GUI, TUI and web) ──────────────────────

def moving_average(values: List[float], window: int) -> List[float]:
    """Centered moving average with edge replication."""
    import numpy as np

    if window < 2 or len(values) < window:
        return values[:]
    arr = np.array(values, dtype=float)
    kernel = np.ones(window) / window
    ma = np.convolve(arr, kernel, mode="same")
    edge = window // 2
    ma[:edge] = arr[edge]
    ma[-edge:] = arr[-edge - 1]
    return ma.tolist()


def detect_peaks(times: List[float], values: List[float], min_prominence: float = 0.05) -> List[Tuple[float, float]]:
    """Local-maxima peak detection with prominence filter. Returns (t, value) list."""
    import numpy as np

    if len(values) < 3:
        return []
    arr = np.array(values)
    t = np.array(times)
    peaks: List[Tuple[float, float]] = []
    for i in range(1, len(arr) - 1):
        if arr[i] > arr[i - 1] and arr[i] >= arr[i + 1]:
            w = min(20, i, len(arr) - 1 - i)
            left_min = arr[max(0, i - w):i].min()
            right_min = arr[i + 1:i + 1 + w].min()
            prom = arr[i] - max(left_min, right_min)
            if prom >= min_prominence:
                peaks.append((float(t[i]), float(arr[i])))
    return peaks


def detect_phases(times: List[float], powers: List[float]) -> List[Tuple[str, float, float, float]]:
    """Simple 3-phase charge detection: ramp-up, steady, taper. Returns (name, t0, t1, avg_p)."""
    import numpy as np

    if len(powers) < 10:
        return []
    arr = np.array(powers)
    n = len(arr)
    third = n // 3
    phases: List[Tuple[str, float, float, float]] = []
    p1 = arr[:third]
    phases.append(("① Розгін", times[0], times[min(third, n - 1)], float(p1.mean())))
    p2 = arr[third:2 * third]
    if len(p2):
        phases.append(("② Стабільна", times[third], times[min(2 * third, n - 1)], float(p2.mean())))
    p3 = arr[2 * third:]
    if len(p3):
        phases.append(("③ Спад", times[2 * third], times[-1], float(p3.mean())))
    return phases


def build_report(
    samples: List[Sample],
    ref_samples: Optional[List[Sample]] = None,
    source: str = "",
    ref_name: str = "",
    ma_window: int = 10,
    peak_sens: float = 0.05,
) -> str:
    """Build a plain-text laboratory analysis report (shared by GUI, TUI, web)."""
    if len(samples) < 2:
        return "Замало даних для звіту (потрібно щонайменше 2 точки)."

    stats = calculate_statistics(samples)
    ch = stats.get("channels", {})
    en = stats.get("energy", {})

    ts = [s.time for s in samples]
    ps = [s.power for s in samples]
    vs = [s.voltage for s in samples]
    peaks = detect_peaks(ts, ps, min_prominence=peak_sens)
    ma_v = moving_average(vs, ma_window)
    ma_i = moving_average([s.current for s in samples], ma_window)

    vpp = (ch.get("voltage", {}).get("max", 0) or 0) - (ch.get("voltage", {}).get("min", 0) or 0)
    ipp = (ch.get("current", {}).get("max", 0) or 0) - (ch.get("current", {}).get("min", 0) or 0)

    phases = detect_phases(ts, ps)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    src = source or "жива сесія"

    report = f"""═══════════════════════════════════════════════════════════
  ЗВІТ АНАЛІЗУ WITRN K2
  Згенеровано: {now}
  Джерело: {src}
═══════════════════════════════════════════════════════════

■ ЗАГАЛЬНА ІНФОРМАЦІЯ
  Кількість точок:      {stats.get('count', 0)}
  Тривалість:           {stats.get('duration_sec', 0):.2f} с
  Середня частота:      {stats.get('count', 0) / max(stats.get('duration_sec', 1), 0.01):.1f} Гц

■ НАПРУГА (VBUS)
  Min:                  {ch.get('voltage', {}).get('min', 0):.4f} В
  Max:                  {ch.get('voltage', {}).get('max', 0):.4f} В
  Середнє (зважене):    {ch.get('voltage', {}).get('avg', 0):.4f} В
  Амплітуда (Vpp):      {vpp:.4f} В
  Сер. ковзне (Ma{ma_window}):  {ma_v[-1] if ma_v else 0:.4f} В

■ СТРУМ (IBUS)
  Min:                  {ch.get('current', {}).get('min', 0):+.4f} А
  Max:                  {ch.get('current', {}).get('max', 0):+.4f} А
  Середнє (зважене):    {ch.get('current', {}).get('avg', 0):+.4f} А
  Амплітуда (Ipp):      {ipp:.4f} А
  Сер. ковзне (Ma{ma_window}):  {ma_i[-1] if ma_i else 0:+.4f} А

■ ПОТУЖНІСТЬ
  Min:                  {ch.get('power', {}).get('min', 0):.4f} Вт
  Max:                  {ch.get('power', {}).get('max', 0):.4f} Вт
  Середнє:              {ch.get('power', {}).get('avg', 0):.4f} Вт

■ ІНТЕГРАЛЬНІ ПОКАЗНИКИ
  Ємність (net):        {en.get('mah_net', 0):.3f} mAh
  Вхідна ємність:       {en.get('mah_forward', 0):.3f} mAh
  Зворотна ємність:      {en.get('mah_reverse', 0):.3f} mAh
  Енергія (net):        {en.get('mwh_net', 0):.3f} mWh
  Вхідна енергія:       {en.get('mwh_forward', 0):.3f} mWh
  Зворотна енергія:      {en.get('mwh_reverse', 0):.3f} mWh

■ АНАЛІЗ ПІКІВ (чутливість: {peak_sens:.3f})
  Знайдено піків:       {len(peaks)}
"""

    if peaks:
        report += "\n  Топ-5 найвищих піків потужності:\n"
        top_peaks = sorted(peaks, key=lambda p: -p[1])[:5]
        for i, (pt, pv) in enumerate(top_peaks, 1):
            report += f"    {i}. t={pt:.2f}с  P={pv:.3f} Вт\n"

    if phases:
        report += "\n■ ФАЗИ ЗАРЯДКИ (детекція за потужністю)\n"
        for phase_name, t0, t1, p_avg in phases:
            report += f"    {phase_name}: {t0:.1f}–{t1:.1f}с  (P≈{p_avg:.2f} Вт)\n"

    if ref_samples and len(ref_samples) >= 2:
        ref_stats = calculate_statistics(ref_samples)
        ref_en = ref_stats.get("energy", {})
        ref_ch = ref_stats.get("channels", {})
        report += f"""
■ ПОРІВНЯННЯ З РЕФЕРЕНСОМ ({ref_name or "референс"})
  Референс точок:       {ref_stats.get('count', 0)}
  Референс тривалість:  {ref_stats.get('duration_sec', 0):.2f} с
  Δ Ємність:            {en.get('mah_net', 0) - ref_en.get('mah_net', 0):+.3f} mAh
  Δ Енергія:            {en.get('mwh_net', 0) - ref_en.get('mwh_net', 0):+.3f} mWh
  Δ V max:              {(ch.get('voltage', {}).get('max', 0) or 0) - (ref_ch.get('voltage', {}).get('max', 0) or 0):+.4f} В
  Δ I max:              {(ch.get('current', {}).get('max', 0) or 0) - (ref_ch.get('current', {}).get('max', 0) or 0):+.4f} А
"""

    report += "\n═══════════════════════════════════════════════════════════\n"
    return report
