"""Pin the window you are using so it stays on top of everything else."""

from __future__ import annotations

import ctypes
import json
import os
import threading
from pathlib import Path

import pystray
from PIL import Image, ImageDraw

user32 = ctypes.windll.user32
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_SHOWWINDOW = 0x0040

APP_DIR = Path(__file__).resolve().parent
CONFIG_PATH = APP_DIR / "config.json"
STARTUP_NAME = "PinWindow.vbs"

pinned: list[int] = []
lock = threading.Lock()


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text('{"start_with_windows": false}\n', encoding="utf-8")
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_config(data: dict) -> None:
    CONFIG_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def startup_path() -> Path:
    return (
        Path(os.environ.get("APPDATA", ""))
        / "Microsoft/Windows/Start Menu/Programs/Startup"
        / STARTUP_NAME
    )


def set_startup(icon, want: bool) -> None:
    p = startup_path()
    script = Path(__file__).resolve()
    try:
        if want:
            p.write_text(
                'Set sh = CreateObject("WScript.Shell")\n'
                f'sh.CurrentDirectory = "{script.parent}"\n'
                f'sh.Run "pythonw ""{script}""", 0, False\n',
                encoding="ascii",
            )
        elif p.exists():
            p.unlink()
        cfg = load_config()
        cfg["start_with_windows"] = want
        save_config(cfg)
        icon.update_menu()
    except OSError:
        pass


def title_of(hwnd: int) -> str:
    n = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(n + 1)
    user32.GetWindowTextW(hwnd, buf, n + 1)
    t = buf.value.strip() or hex(hwnd)
    return t[:40] + ("…" if len(t) > 40 else "")


def apply_top(hwnd: int, on: bool) -> None:
    user32.SetWindowPos(
        hwnd,
        HWND_TOPMOST if on else HWND_NOTOPMOST,
        0,
        0,
        0,
        0,
        SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW,
    )


def pin_foreground(icon=None, item=None) -> None:
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return
    apply_top(hwnd, True)
    with lock:
        if hwnd not in pinned:
            pinned.append(hwnd)
    if icon:
        try:
            icon.update_menu()
        except Exception:
            pass


def unpin(hwnd: int):
    def _go(icon, item):
        apply_top(hwnd, False)
        with lock:
            if hwnd in pinned:
                pinned.remove(hwnd)
        try:
            icon.update_menu()
        except Exception:
            pass

    return _go


def unpin_all(icon, item=None) -> None:
    with lock:
        ids = list(pinned)
        pinned.clear()
    for h in ids:
        try:
            apply_top(h, False)
        except Exception:
            pass
    try:
        icon.update_menu()
    except Exception:
        pass


def quit_app(icon, _item=None) -> None:
    unpin_all(icon)
    icon.stop()


def menu(icon):
    with lock:
        ids = list(pinned)
    items = [
        pystray.MenuItem("Click a window, then Pin", None, enabled=False),
        pystray.MenuItem("Pin foreground window", pin_foreground),
        pystray.MenuItem("Unpin all", unpin_all),
        pystray.MenuItem(
            "Start with Windows",
            lambda i, _: set_startup(i, not startup_path().exists()),
            checked=lambda _: startup_path().exists(),
        ),
        pystray.Menu.SEPARATOR,
    ]
    if not ids:
        items.append(pystray.MenuItem("(nothing pinned)", None, enabled=False))
    else:
        for h in ids:
            items.append(pystray.MenuItem("Unpin: " + title_of(h), unpin(h)))
    items.append(pystray.Menu.SEPARATOR)
    items.append(pystray.MenuItem("Quit", quit_app))
    return pystray.Menu(*items)


def icon_img():
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.polygon([(32, 6), (54, 28), (32, 50), (10, 28)], fill=(180, 70, 70, 255))
    d.ellipse((24, 20, 40, 36), fill="white")
    return img


def main() -> None:
    load_config()
    icon = pystray.Icon("PinWindow", icon_img(), "Pin window", menu=pystray.Menu(lambda: menu(icon)))
    icon.run()


if __name__ == "__main__":
    main()
