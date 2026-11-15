"""WITRN K2 Command-Line Interface (CLI).

Supports device diagnostic inspection, live terminal monitoring, headless recording,
file analysis, and web dashboard launching.
"""
import argparse
from datetime import datetime
import os
from pathlib import Path
import sys
import time

# Cross-platform Windows console compatibility (ANSI color escape codes & UTF-8)
if sys.platform == "win32":
    os.system("")  # Enables Virtual Terminal Processing in Windows Console
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

from .core import (
    calculate_statistics,
    decode_report,
    export_official_csv,
    export_standard_csv,
    find_k2_device,
    import_official_csv,
    open_transport,
)
from .core.exporter import read_sqlite_samples
from .core.recorder import AutoStopRule, Recorder


def cmd_info(args):
    """Inspect and report WITRN K2 device status and permissions."""
    print("=== Діагностика підключення WITRN K2 ===")
    dev = find_k2_device()
    if not dev:
        print("❌ Пристрій WITRN K2 (0716:5060) НЕ знайдено на шині USB.")
        print("   Перевірте підключення кабелю USB до порту CC1/HID тестера.")
        sys.exit(1)

    print(f"✓ Пристрій знайдено: {dev.get('name')}")
    print(f"  Вузол у системі:   {dev.get('path')}")
    print(f"  Серійний номер:    {dev.get('serial')}")
    print(f"  Тип інтерфейсу:    {dev.get('type')}")
    print(f"  Права на читання:  {'✓ ТАК' if dev.get('readable') else '❌ НІ'}")
    print(f"  Права на запис:    {'✓ ТАК' if dev.get('writable') else '❌ НІ'}")

    if not dev.get("readable") or not dev.get("writable"):
        print("\n⚠️ УВАГА: Немає прав доступу до пристрою.")
        if sys.platform == "win32":
            print("   На Windows переконайтеся, що тестер не зайнятий іншою програмою")
            print("   (наприклад, оригінальним додатком WITRN). Закрийте інші програми та спробуйте знову.")
        else:
            print("   Щоб надати права, виконайте:")
            print("     sudo ./setup_udev.sh")
            print("   або одноразово:")
            print(f"     sudo chmod 666 {dev.get('path')}")
        sys.exit(1)
    else:
        print("\n✓ Пристрій готовий до зчитування даних!")


def cmd_gui(args):
    """Launch native desktop GUI (PyQt6)."""
    from .gui import main as gui_main
    gui_main()


def cmd_dash(args):
    """Full-screen terminal dashboard (rich TUI)."""
    from .tui import run_dashboard
    try:
        trans, info = open_transport(force_simulator=args.simulator)
    except Exception as exc:
        print(f"Помилка підключення: {exc}")
        sys.exit(1)

    auto_stop = None
    if args.auto_stop:
        auto_stop = {
            "enabled": True,
            "kind": args.auto_kind,
            "threshold": args.threshold,
            "duration": args.trigger_duration,
        }

    run_dashboard(
        trans, info,
        rate=args.rate if args.record else 0,
        record=args.record,
        out_path=args.out,
        auto_stop=auto_stop,
    )


def cmd_live(args):
    """Live ASCII dashboard in terminal."""
    try:
        trans, info = open_transport(force_simulator=args.simulator)
    except Exception as exc:
        print(f"Помилка підключення: {exc}")
        sys.exit(1)

    print(f"Підключено до {info.get('name')} ({info.get('path')}). Натисніть Ctrl+C для виходу.\n")
    started = time.monotonic()
    sample_count = 0

    try:
        while True:
            raw = trans.read(50)
            now = time.monotonic()
            if raw:
                s = decode_report(raw, now - started)
                if s:
                    sample_count += 1
                    res_str = f"{s.resistance:.2f}Ω" if s.resistance is not None else "---"
                    temp_in_str = f"{s.temp_in:.1f}°C" if s.temp_in is not None else "--.-"
                    temp_out_str = f"{s.temp_out:.1f}°C" if s.temp_out is not None else "--.-"

                    # ANSI rewrite line
                    sys.stdout.write(
                        f"\r\033[K"
                        f"⚡ \033[1;36m{s.voltage:7.4f} V\033[0m | "
                        f"📈 \033[1;32m{s.current:7.4f} A\033[0m | "
                        f"🔥 \033[1;33m{s.power:7.4f} W\033[0m | "
                        f"Ω: {res_str:<7} | "
                        f"D+: {s.dp:.2f}V D-: {s.dn:.2f}V | "
                        f"T: {temp_in_str}/{temp_out_str} | "
                        f"Ah: {s.ah:.4f} Wh: {s.wh:.4f} | "
                        f"#{sample_count}"
                    )
                    sys.stdout.flush()
            time.sleep(0.01)
    except KeyboardInterrupt:
        print("\n\nЗупинено користувачем.")
    finally:
        trans.close()


def cmd_record(args):
    """Record telemetry headlessly to an SQLite or CSV file."""
    try:
        trans, info = open_transport(force_simulator=args.simulator)
    except Exception as exc:
        print(f"Помилка підключення: {exc}")
        sys.exit(1)

    out_path = Path(args.out).resolve()
    recorder = Recorder(out_path.parent)

    auto_rule = AutoStopRule(
        enabled=args.auto_stop,
        kind=args.auto_kind,
        threshold=args.threshold,
        duration=args.trigger_duration,
    )

    db_path = recorder.start(session_name=out_path.stem, rate=args.rate, auto_rule=auto_rule)
    print(f"🔴 Почато запис у: {db_path}")
    print(f"   Частота: {args.rate if args.rate > 0 else 'Макс'} Гц | Ліміт часу: {args.duration or 'Необмежено'} с")

    started = time.monotonic()
    try:
        while True:
            now = time.monotonic()
            elapsed = now - started
            if args.duration and elapsed >= args.duration:
                print("\nДосягнуто ліміту тривалості.")
                break

            raw = trans.read(50)
            if raw:
                s = decode_report(raw, elapsed)
                if s:
                    auto_stopped = recorder.feed(s)
                    sys.stdout.write(
                        f"\r\033[KЗапис: {elapsed:6.1f}s | "
                        f"{s.voltage:6.3f}V {s.current:6.3f}A {s.power:6.3f}W | "
                        f"Точок: {recorder.session.count if recorder.session else 0}"
                    )
                    sys.stdout.flush()
                    if auto_stopped:
                        print("\nСпрацювала умова автозупинки.")
                        break
            time.sleep(0.005)
    except KeyboardInterrupt:
        print("\n\nЗапис перервано користувачем.")
    finally:
        saved_file = recorder.stop()
        trans.close()
        print(f"✓ Запис успішно збережено: {saved_file}")

        # If user wanted a CSV export immediately
        if args.format == "csv":
            csv_file = saved_file.with_suffix(".csv")
            samples = list(read_sqlite_samples(saved_file))
            export_standard_csv(samples, csv_file)
            print(f"✓ Експортовано в CSV: {csv_file}")
        elif args.format == "witrn_csv":
            csv_file = saved_file.with_name(f"{saved_file.stem}_witrn.csv")
            samples = list(read_sqlite_samples(saved_file))
            export_official_csv(samples, csv_file)
            print(f"✓ Експортовано в офіційний WITRN CSV: {csv_file}")


def cmd_analyze(args):
    """Analyze an SQLite or CSV recording file and print a summary table."""
    file_path = Path(args.file).resolve()
    if not file_path.exists():
        print(f"Файл не знайдено: {file_path}")
        sys.exit(1)

    print(f"Аналіз файлу: {file_path.name}")
    if file_path.suffix.lower() == ".sqlite":
        samples = list(read_sqlite_samples(file_path))
    elif file_path.suffix.lower() == ".csv":
        samples = import_official_csv(file_path)
    else:
        print("Підтримуються тільки .sqlite та .csv файли.")
        sys.exit(1)

    if not samples:
        print("У файлі немає вимірювань.")
        return

    stats = calculate_statistics(samples)
    print("\n" + "=" * 60)
    print(f" ЗВЕДЕНИЙ ЗВІТ АНАЛІЗУ ({stats['count']} точок, {stats['duration_sec']:.2f} сек)")
    print("=" * 60)
    print(f"{'Канал':<16} | {'Min':<8} | {'Max':<8} | {'Avg':<8} | {'Vpp / Ipp':<8}")
    print("-" * 60)

    for ch_name, key, unit in (
        ("Напруга (VBUS)", "voltage", "V"),
        ("Струм (IBUS)", "current", "A"),
        ("Потужність", "power", "W"),
        ("D+ Напруга", "dp", "V"),
        ("D- Напруга", "dn", "V"),
        ("Внутрішня темп.", "temp_in", "°C"),
        ("Зовнішня темп.", "temp_out", "°C"),
    ):
        st = stats["channels"].get(key)
        if st and st["min"] is not None:
            print(f"{ch_name:<16} | {st['min']:<8.3f} | {st['max']:<8.3f} | {st['avg']:<8.3f} | {st['vpp']:<8.3f}")

    print("-" * 60)
    en = stats["energy"]
    print(f"🔋 Інтегрована ємність:  {en['mah_net']:>10.2f} mAh (Вхідна: {en['mah_forward']:.2f}, Вихідна: {en['mah_reverse']:.2f})")
    print(f"⚡ Інтегрована енергія:  {en['mwh_net']:>10.2f} mWh (Вхідна: {en['mwh_forward']:.2f}, Вихідна: {en['mwh_reverse']:.2f})")
    if stats["resistance"]["avg"] is not None:
        print(f"Ω Середній опір:       {stats['resistance']['avg']:>10.2f} Ω (Min: {stats['resistance']['min']}, Max: {stats['resistance']['max']})")
    print("=" * 60 + "\n")


def cmd_serve(args):
    """Launch the FastAPI Web Dashboard."""
    import threading
    import uvicorn
    import webbrowser
    url = f"http://{args.host}:{args.port}"
    print(f"🚀 Запуск веб-інтерфейсу WITRN K2 на: {url}")

    if args.open_browser:
        def open_delayed():
            time.sleep(1.2)
            try:
                webbrowser.open(url)
            except Exception:
                pass
        threading.Thread(target=open_delayed, daemon=True).start()

    uvicorn.run("witrn_k2.web.app:app", host=args.host, port=args.port, log_level="info")


def cmd_menu(args):
    """Interactive launcher menu."""
    while True:
        print("\n" + "=" * 62)
        print("⚡ WITRN K2 USB Tester — Меню швидкого вибору")
        print("=" * 62)
        print(" 1) 🌐 Веб-інтерфейс (Web Dashboard: http://127.0.0.1:8000)")
        print(" 2) 🖥️  Графічний додаток (PyQt6 Desktop GUI)")
        print(" 3) 📊 Термінальний дашборд (Rich TUI)")
        print(" 4) 🎮 Термінальний дашборд (Режим СИМУЛЯТОРА)")
        print(" 5) ⚡ Компактний однорядковий монітор (Live)")
        print(" 6) 🔋 Запис заряджання акумулятора (Автозупинка при <50мА)")
        print(" 7) 🚀 Швидкісний запис (100 Гц)")
        print(" 8) 🔍 Діагностика підключення тестера (info)")
        print(" 9) 📈 Аналіз останнього збереженого запису")
        print(" 0) ❌ Вихід")
        print("=" * 62)
        try:
            choice = input("Оберіть дію [0-9]: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nВихід.")
            break

        if choice == "1":
            from argparse import Namespace
            cmd_serve(Namespace(host="127.0.0.1", port=8000, open_browser=True))
        elif choice == "2":
            from argparse import Namespace
            cmd_gui(Namespace())
        elif choice == "3":
            from argparse import Namespace
            cmd_dash(Namespace(simulator=False, record=False, out="recordings/dash.sqlite", rate=10, auto_stop=False))
        elif choice == "4":
            from argparse import Namespace
            cmd_dash(Namespace(simulator=True, record=False, out="recordings/dash.sqlite", rate=10, auto_stop=False))
        elif choice == "5":
            from argparse import Namespace
            cmd_live(Namespace(simulator=False))
        elif choice == "6":
            from argparse import Namespace
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            Path("recordings").mkdir(parents=True, exist_ok=True)
            out_file = f"recordings/charge_{ts}.sqlite"
            cmd_record(Namespace(
                out=out_file, duration=None, rate=10, format="witrn_csv",
                auto_stop=True, auto_kind="current", threshold=0.05,
                trigger_duration=10.0, simulator=False
            ))
        elif choice == "7":
            from argparse import Namespace
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            Path("recordings").mkdir(parents=True, exist_ok=True)
            out_file = f"recordings/highspeed_100hz_{ts}.sqlite"
            cmd_record(Namespace(
                out=out_file, duration=None, rate=100, format="sqlite",
                auto_stop=False, auto_kind="current", threshold=0.05,
                trigger_duration=10.0, simulator=False
            ))
        elif choice == "8":
            from argparse import Namespace
            try:
                cmd_info(Namespace())
            except SystemExit:
                pass
            input("\nНатисніть Enter для повернення в меню...")
        elif choice == "9":
            rec_dir = Path("recordings")
            files = sorted(rec_dir.glob("*.sqlite"), key=lambda p: p.stat().st_mtime, reverse=True) if rec_dir.exists() else []
            if files:
                from argparse import Namespace
                cmd_analyze(Namespace(file=str(files[0])))
            else:
                print("У папці recordings/ ще немає збережених сесій.")
            input("\nНатисніть Enter для повернення в меню...")
        elif choice in ("0", "q", "Q"):
            print("До побачення!")
            break
        else:
            print("Невірний вибір. Спробуйте ще раз.")


def main():
    parser = argparse.ArgumentParser(
        description="WITRN K2 USB Tester Tool & Analyzer",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # info
    p_info = subparsers.add_parser("info", help="Діагностика підключення та прав доступу K2")
    p_info.set_defaults(func=cmd_info)

    # gui
    p_gui = subparsers.add_parser("gui", help="Нативний GUI-додаток (PyQt6)")
    p_gui.set_defaults(func=cmd_gui)

    # dash
    p_dash = subparsers.add_parser("dash", help="Повноекранний термінальний дашборд (TUI)")
    p_dash.add_argument("--simulator", action="store_true", help="Режим симулятора")
    p_dash.add_argument("--record", action="store_true", help="Паралельно записувати у SQLite")
    p_dash.add_argument("-o", "--out", default="recordings/dashboard_capture.sqlite", help="Вихідний файл запису")
    p_dash.add_argument("-r", "--rate", type=int, default=10, choices=[0, 1, 10, 50, 100], help="Частота запису (Гц)")
    p_dash.add_argument("--auto-stop", action="store_true", help="Автозупинка запису за порогом")
    p_dash.add_argument("--auto-kind", choices=["current", "power"], default="current")
    p_dash.add_argument("--threshold", type=float, default=0.05, help="Поріг автозупинки")
    p_dash.add_argument("--trigger-duration", type=float, default=10.0, help="Час нижче порогу (с)")
    p_dash.set_defaults(func=cmd_dash)

    # live
    p_live = subparsers.add_parser("live", help="Живий термінальний монітор (однорядковий)")
    p_live.add_argument("--simulator", action="store_true", help="Запустити в режимі симулятора")
    p_live.set_defaults(func=cmd_live)

    # record
    p_rec = subparsers.add_parser("record", help="Автономний запис у файл")
    p_rec.add_argument("-o", "--out", default="recordings/capture.sqlite", help="Вихідний файл (.sqlite або .csv)")
    p_rec.add_argument("-d", "--duration", type=float, default=None, help="Тривалість запису в секундах")
    p_rec.add_argument("-r", "--rate", type=int, default=10, choices=[0, 1, 10, 50, 100], help="Частота (Гц)")
    p_rec.add_argument("--format", choices=["sqlite", "csv", "witrn_csv"], default="sqlite", help="Формат збереження")
    p_rec.add_argument("--auto-stop", action="store_true", help="Увімкнути автозупинку")
    p_rec.add_argument("--auto-kind", choices=["current", "power"], default="current")
    p_rec.add_argument("--threshold", type=float, default=0.05, help="Поріг автозупинки")
    p_rec.add_argument("--trigger-duration", type=float, default=10.0, help="Час нижче порогу для спрацювання (с)")
    p_rec.add_argument("--simulator", action="store_true", help="Використовувати симулятор")
    p_rec.set_defaults(func=cmd_record)

    # analyze
    p_ana = subparsers.add_parser("analyze", help="Аналіз збереженого файлу запису")
    p_ana.add_argument("file", help="Шлях до файлу .sqlite або .csv")
    p_ana.set_defaults(func=cmd_analyze)

    # serve
    p_srv = subparsers.add_parser("serve", help="Запуск сучасного веб-інтерфейсу")
    p_srv.add_argument("--host", default="127.0.0.1", help="Хост")
    p_srv.add_argument("--port", type=int, default=8000, help="Порт")
    p_srv.add_argument("--open-browser", action="store_true", default=True, help="Автоматично відкрити браузер")
    p_srv.set_defaults(func=cmd_serve)

    # menu
    p_menu = subparsers.add_parser("menu", help="Інтерактивне меню вибору режиму запуску")
    p_menu.set_defaults(func=cmd_menu)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
