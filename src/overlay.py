"""Always-on-top button: snap the last app left and open Gemini on the right."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from paths import app_dir

ROOT = app_dir()
STATE_FILE = ROOT / "overlay-state.json"
OLD_PID_FILE = ROOT / "overlay.pid"
OLD_POS_FILE = ROOT / "overlay-pos.json"
TITLE = "Split View"
WIDTH = 128
HEIGHT = 44
RADIUS = 18
DRAG_PX = 10
FILL = "#2b6cb0"
FILL_OK = "#2f855a"
FILL_NG = "#c53030"
CHROMA = "#ff00fe"
MONITOR_DEFAULTTONULL = 0
MONITORINFOF_PRIMARY = 1


def _dpi_aware() -> None:
    if sys.platform != "win32":
        return
    try:
        from ctypes import WinDLL

        WinDLL("shcore").SetProcessDpiAwareness(2)
    except Exception:
        try:
            from ctypes import WinDLL

            WinDLL("user32").SetProcessDPIAware()
        except Exception:
            pass


def _pid_running(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        import ctypes

        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
        if handle:
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _empty_state() -> dict:
    return {"pid": None, "x": None, "y": None}


def _write_state(state: dict) -> None:
    payload = {
        "pid": state.get("pid"),
        "x": state.get("x"),
        "y": state.get("y"),
    }
    STATE_FILE.write_text(json.dumps(payload), encoding="utf-8")


def _read_state() -> dict:
    state = _empty_state()
    if STATE_FILE.exists():
        try:
            data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                if "pid" in data:
                    state["pid"] = data["pid"]
                if "x" in data:
                    state["x"] = data["x"]
                if "y" in data:
                    state["y"] = data["y"]
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            pass

    migrated = False
    if OLD_PID_FILE.exists():
        try:
            state["pid"] = int(OLD_PID_FILE.read_text(encoding="utf-8").strip())
            migrated = True
        except (OSError, ValueError):
            pass
        try:
            OLD_PID_FILE.unlink()
        except OSError:
            pass
    if OLD_POS_FILE.exists():
        try:
            pos = json.loads(OLD_POS_FILE.read_text(encoding="utf-8"))
            state["x"] = int(pos["x"])
            state["y"] = int(pos["y"])
            migrated = True
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            pass
        try:
            OLD_POS_FILE.unlink()
        except OSError:
            pass
    if migrated:
        try:
            _write_state(state)
        except OSError:
            pass
    return state


def overlay_pid() -> int | None:
    raw = _read_state().get("pid")
    try:
        pid = int(raw)
    except (TypeError, ValueError):
        return None
    if _pid_running(pid):
        return pid
    return None


def overlay_running() -> bool:
    pid = overlay_pid()
    return pid is not None and pid != os.getpid()


def _launch_self(extra_args: list[str] | None = None) -> list[str]:
    if getattr(sys, "frozen", False):
        return [str(Path(sys.executable).resolve()), *(extra_args or [])]
    return [sys.executable, str(Path(__file__).resolve().parent / "main.py"), *(extra_args or [])]


def start_overlay_detached() -> None:
    if overlay_running():
        return
    args = _launch_self(["--overlay"])
    kwargs: dict = {"cwd": str(ROOT), "close_fds": True}
    if sys.platform == "win32":
        flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(
            subprocess, "CREATE_NEW_PROCESS_GROUP", 0
        )
        kwargs["creationflags"] = flags
        kwargs["stdout"] = subprocess.DEVNULL
        kwargs["stderr"] = subprocess.DEVNULL
        subprocess.Popen(args, **kwargs)
    else:
        subprocess.Popen(args, start_new_session=True, **kwargs)
    deadline = time.monotonic() + 4
    while time.monotonic() < deadline:
        if overlay_running():
            return
        time.sleep(0.1)


def _stop_previous() -> None:
    pid = overlay_pid()
    if not pid or pid == os.getpid():
        return
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/F"],
            capture_output=True,
            check=False,
        )
    else:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
    time.sleep(0.2)


def _write_pid() -> None:
    state = _read_state()
    state["pid"] = os.getpid()
    try:
        _write_state(state)
    except OSError:
        pass


def _clear_pid() -> None:
    state = _read_state()
    try:
        current = int(state.get("pid"))
    except (TypeError, ValueError):
        current = None
    if current != os.getpid():
        return
    state["pid"] = None
    try:
        _write_state(state)
    except OSError:
        pass


def _load_pos() -> tuple[int, int] | None:
    state = _read_state()
    try:
        if state.get("x") is None or state.get("y") is None:
            return None
        return int(state["x"]), int(state["y"])
    except (TypeError, ValueError):
        return None


def _save_pos(x: int, y: int) -> None:
    state = _read_state()
    state["x"] = int(x)
    state["y"] = int(y)
    try:
        _write_state(state)
    except OSError:
        pass


def _win_structs():
    from ctypes import Structure, wintypes

    class RECT(wintypes.RECT):
        pass

    class MONITORINFO(Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("rcMonitor", RECT),
            ("rcWork", RECT),
            ("dwFlags", wintypes.DWORD),
        ]

    return RECT, MONITORINFO


def _work_areas() -> list[tuple[int, int, int, int, bool]]:
    _dpi_aware()
    if sys.platform != "win32":
        return [(0, 0, 1600, 900, True)]

    from ctypes import WINFUNCTYPE, WinDLL, byref, sizeof, wintypes

    user32 = WinDLL("user32", use_last_error=True)
    RECT, MONITORINFO = _win_structs()
    areas: list[tuple[int, int, int, int, bool]] = []
    MONITORENUMPROC = WINFUNCTYPE(
        wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC, wintypes.LPRECT, wintypes.LPARAM
    )

    def callback(_hmon, _hdc, _lprc, _lparam):
        info = MONITORINFO()
        info.cbSize = sizeof(MONITORINFO)
        if user32.GetMonitorInfoW(_hmon, byref(info)):
            work = info.rcWork
            areas.append(
                (
                    int(work.left),
                    int(work.top),
                    int(work.right),
                    int(work.bottom),
                    bool(info.dwFlags & MONITORINFOF_PRIMARY),
                )
            )
        return True

    cb = MONITORENUMPROC(callback)
    user32.EnumDisplayMonitors(None, None, cb, 0)
    return areas or [(0, 0, 1600, 900, True)]


def _default_pos(areas: list[tuple[int, int, int, int, bool]] | None = None) -> tuple[int, int]:
    monitors = areas or _work_areas()
    primary = next((a for a in monitors if a[4]), monitors[0] if monitors else (0, 0, 1600, 900, True))
    left, top, right, bottom, _ = primary
    x = max(left, right - WIDTH - 24)
    y = max(top, bottom - HEIGHT - 36)
    return x, y


def _rect_on_any_monitor(left: int, top: int, right: int, bottom: int) -> bool:
    if sys.platform != "win32":
        areas = _work_areas()
        cx = (left + right) // 2
        cy = (top + bottom) // 2
        return any(a[0] <= cx < a[2] and a[1] <= cy < a[3] for a in areas)

    from ctypes import WinDLL, byref

    user32 = WinDLL("user32", use_last_error=True)
    RECT, _MONITORINFO = _win_structs()
    rect = RECT()
    rect.left = int(left)
    rect.top = int(top)
    rect.right = int(right)
    rect.bottom = int(bottom)
    return bool(user32.MonitorFromRect(byref(rect), MONITOR_DEFAULTTONULL))


def _visible_pos(x: int, y: int) -> tuple[int, int]:
    areas = _work_areas()
    if _rect_on_any_monitor(x, y, x + WIDTH, y + HEIGHT):
        return x, y
    return _default_pos(areas)


class Overlay:
    def __init__(self) -> None:
        import tkinter as tk

        _dpi_aware()
        self.tk = tk
        self.root = tk.Tk()
        self.root.title(TITLE)
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.resizable(False, False)
        self.root.configure(bg=CHROMA)
        if sys.platform == "win32":
            self.root.wm_attributes("-transparentcolor", CHROMA)

        saved = _load_pos()
        x, y = _visible_pos(*(saved if saved else _default_pos()))
        self.root.geometry(f"{WIDTH}x{HEIGHT}+{x}+{y}")
        if saved and (x, y) != saved:
            _save_pos(x, y)

        font = ("Yu Gothic UI", 11, "bold") if sys.platform == "win32" else ("Hiragino Sans", 12, "bold")
        self.canvas = tk.Canvas(
            self.root,
            width=WIDTH,
            height=HEIGHT,
            bg=CHROMA,
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack()
        self._pill = self._draw_pill(FILL)
        self.canvas.create_text(
            WIDTH // 2,
            HEIGHT // 2,
            text=TITLE,
            fill="#ffffff",
            font=font,
        )

        self._press: tuple[int, int] | None = None
        self._off = (0, 0)
        self._dragged = False
        self._gesture_done = False
        self._busy = False
        self.remembered_hwnd: int | None = None
        self.self_hwnd: int | None = None

        for seq, handler in (
            ("<ButtonPress-1>", self._on_press),
            ("<B1-Motion>", self._on_drag),
            ("<ButtonRelease-1>", self._on_release),
        ):
            self.canvas.bind(seq, handler)
        self.root.bind("<Escape>", lambda _e: self.root.destroy())
        self.root.after(50, self._apply_round_region)
        self.root.after(200, self._poll)
        self.root.after(1000, self._ensure_on_screen)
        self.root.protocol("WM_DELETE_WINDOW", self.root.destroy)

    def _window_rect(self) -> tuple[int, int, int, int]:
        x = int(self.root.winfo_x())
        y = int(self.root.winfo_y())
        if sys.platform == "win32":
            try:
                from ctypes import WinDLL, byref

                user32 = WinDLL("user32", use_last_error=True)
                RECT, _MONITORINFO = _win_structs()
                hwnd = int(self.root.winfo_id())
                rect = RECT()
                if user32.GetWindowRect(hwnd, byref(rect)):
                    return int(rect.left), int(rect.top), int(rect.right), int(rect.bottom)
            except Exception:
                pass
        return x, y, x + WIDTH, y + HEIGHT

    def _ensure_on_screen(self) -> None:
        try:
            if self._dragged or self._press is not None:
                self.root.after(1000, self._ensure_on_screen)
                return
            left, top, right, bottom = self._window_rect()
            if not _rect_on_any_monitor(left, top, right, bottom):
                nx, ny = _default_pos()
                self.root.geometry(f"{WIDTH}x{HEIGHT}+{nx}+{ny}")
                _save_pos(nx, ny)
        except Exception:
            pass
        self.root.after(1000, self._ensure_on_screen)

    def _draw_pill(self, color: str) -> int:
        r = RADIUS
        w = WIDTH - 1
        h = HEIGHT - 1
        return self.canvas.create_polygon(
            r, 0, w - r, 0, w, 0, w, r, w, h - r, w, h, w - r, h, r, h, 0, h, 0, h - r, 0, r, 0, 0, r, 0,
            smooth=True,
            fill=color,
            outline=color,
        )

    def _apply_round_region(self) -> None:
        if sys.platform != "win32":
            return
        try:
            import ctypes

            self.root.update_idletasks()
            hwnd = int(self.root.winfo_id())
            w = max(WIDTH, int(self.root.winfo_width()))
            h = max(HEIGHT, int(self.root.winfo_height()))
            hrgn = ctypes.windll.gdi32.CreateRoundRectRgn(0, 0, w + 1, h + 1, RADIUS * 2, RADIUS * 2)
            ctypes.windll.user32.SetWindowRgn(hwnd, hrgn, True)
        except Exception:
            pass

    def _own_hwnd(self) -> int | None:
        if sys.platform != "win32":
            return None
        if self.self_hwnd:
            return self.self_hwnd
        try:
            self.root.update_idletasks()
            frame = self.root.wm_frame()
            if frame:
                self.self_hwnd = int(frame, 16)
                return self.self_hwnd
        except (ValueError, self.tk.TclError):
            pass
        return None

    def _poll(self) -> None:
        try:
            import winsplit

            hwnd = winsplit.foreground_hwnd()
            own = self._own_hwnd()
            if hwnd and hwnd != own:
                title = winsplit.window_title(hwnd)
                if title and TITLE not in title:
                    self.remembered_hwnd = hwnd
        except Exception:
            pass
        self.root.after(200, self._poll)

    def _on_press(self, event) -> None:
        self._press = (event.x_root, event.y_root)
        self._off = (event.x_root - self.root.winfo_x(), event.y_root - self.root.winfo_y())
        self._dragged = False
        self._gesture_done = False

    def _on_drag(self, event) -> None:
        if self._press is None or self._gesture_done:
            return
        if abs(event.x_root - self._press[0]) > DRAG_PX or abs(event.y_root - self._press[1]) > DRAG_PX:
            self._dragged = True
        if self._dragged:
            self.root.geometry(f"+{event.x_root - self._off[0]}+{event.y_root - self._off[1]}")

    def _on_release(self, _event) -> None:
        if self._gesture_done:
            return
        self._gesture_done = True
        dragged = self._dragged
        self._press = None
        self._dragged = False
        if dragged:
            _save_pos(self.root.winfo_x(), self.root.winfo_y())
            return
        if self._busy:
            return
        self._run_split()

    def _set_fill(self, color: str) -> None:
        self.canvas.itemconfigure(self._pill, fill=color, outline=color)

    def _flash(self, ok: bool) -> None:
        self._set_fill(FILL_OK if ok else FILL_NG)
        self.root.after(500, lambda: self._set_fill(FILL))

    def _unlock(self) -> None:
        self._busy = False

    def _run_split(self) -> None:
        if self._busy:
            return
        self._busy = True
        from split_gemini import run

        try:
            result = run(hwnd=self.remembered_hwnd)
            self._flash(bool(result.get("ok")))
        finally:
            self.root.after(700, self._unlock)

    def run(self) -> None:
        try:
            self.root.mainloop()
        finally:
            _clear_pid()


def main() -> int:
    _dpi_aware()
    _stop_previous()
    _write_pid()
    Overlay().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
