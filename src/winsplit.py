"""Place windows on exact left/right halves of the same monitor."""

from __future__ import annotations

import os
import time
from ctypes import Structure, WINFUNCTYPE, WinDLL, byref, create_unicode_buffer, sizeof, wintypes
from typing import Any


user32 = WinDLL("user32", use_last_error=True)
kernel32 = WinDLL("kernel32", use_last_error=True)
dwmapi = WinDLL("dwmapi")
WNDENUMPROC = WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

SW_RESTORE = 9
MONITOR_DEFAULTTONEAREST = 2
SWP_SHOWWINDOW = 0x0040
SWP_NOZORDER = 0x0004
DWMWA_EXTENDED_FRAME_BOUNDS = 9
GW_HWNDNEXT = 2
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
SPI_GETWORKAREA = 0x0030

LEFT_KEYS = ["ヒートマップ", "ダッシュボード", "投資クオンツ"]
SKIP_CLASSES = {
    "Progman",
    "WorkerW",
    "Shell_TrayWnd",
    "Shell_SecondaryTrayWnd",
    "NotifyIconOverflowWindow",
}


class RECT(wintypes.RECT):
    pass


class MONITORINFO(Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", RECT),
        ("rcWork", RECT),
        ("dwFlags", wintypes.DWORD),
    ]


def _dpi_aware() -> None:
    try:
        WinDLL("shcore").SetProcessDpiAwareness(2)
    except Exception:
        try:
            user32.SetProcessDPIAware()
        except Exception:
            pass


def window_title(hwnd: int) -> str:
    length = user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return ""
    buf = create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value


def _is_candidate(hwnd: int) -> bool:
    return bool(user32.IsWindowVisible(hwnd)) and not bool(user32.IsIconic(hwnd))


def _window_area(hwnd: int) -> int:
    rect = RECT()
    if not user32.GetWindowRect(hwnd, byref(rect)):
        return 0
    return max(0, rect.right - rect.left) * max(0, rect.bottom - rect.top)


def _enum_windows() -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []

    def callback(hwnd: int, _lparam: int) -> bool:
        if _is_candidate(hwnd):
            title = window_title(hwnd)
            if title:
                found.append((hwnd, title))
        return True

    cb = WNDENUMPROC(callback)
    user32.EnumWindows(cb, 0)
    return found


def _work_area(hwnd: int) -> RECT:
    monitor = user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
    info = MONITORINFO()
    info.cbSize = sizeof(MONITORINFO)
    if user32.GetMonitorInfoW(monitor, byref(info)):
        return info.rcWork
    work = RECT()
    work.left = 0
    work.top = 0
    work.right = user32.GetSystemMetrics(78) or 1600
    work.bottom = user32.GetSystemMetrics(79) or 900
    return work


def _outer_rect(hwnd: int) -> RECT:
    rect = RECT()
    user32.GetWindowRect(hwnd, byref(rect))
    return rect


def _visible_rect(hwnd: int) -> RECT:
    rect = RECT()
    if dwmapi.DwmGetWindowAttribute(hwnd, DWMWA_EXTENDED_FRAME_BOUNDS, byref(rect), sizeof(rect)) != 0:
        user32.GetWindowRect(hwnd, byref(rect))
    return rect


def _as_box(rect: RECT) -> dict[str, int]:
    return {
        "left": int(rect.left),
        "top": int(rect.top),
        "width": int(rect.right - rect.left),
        "height": int(rect.bottom - rect.top),
    }


def exact_halves(work: RECT) -> tuple[dict[str, int], dict[str, int]]:
    total_w = int(work.right - work.left)
    total_h = int(work.bottom - work.top)
    left_w = total_w // 2
    right_w = total_w - left_w
    left = {"left": int(work.left), "top": int(work.top), "width": left_w, "height": total_h}
    right = {"left": int(work.left) + left_w, "top": int(work.top), "width": right_w, "height": total_h}
    return left, right


def place_visible(hwnd: int, box: dict[str, int]) -> None:
    x, y, w, h = box["left"], box["top"], box["width"], box["height"]
    user32.ShowWindow(hwnd, SW_RESTORE)
    user32.SetWindowPos(hwnd, None, x, y, w, h, SWP_SHOWWINDOW | SWP_NOZORDER)
    outer = _outer_rect(hwnd)
    vis = _visible_rect(hwnd)
    pad_l = vis.left - outer.left
    pad_t = vis.top - outer.top
    pad_r = outer.right - vis.right
    pad_b = outer.bottom - vis.bottom
    user32.SetWindowPos(
        hwnd,
        None,
        x - pad_l,
        y - pad_t,
        w + pad_l + pad_r,
        h + pad_t + pad_b,
        SWP_SHOWWINDOW | SWP_NOZORDER,
    )


def pick_window(
    title: str = "",
    extra_keys: list[str] | None = None,
    exclude: set[int] | None = None,
) -> int | None:
    needle = (title or "").strip()
    keys = [needle] if needle else []
    if extra_keys:
        keys.extend(extra_keys)
    keys = [key for key in keys if key]
    skip = exclude or set()

    foreground = user32.GetForegroundWindow()
    if foreground and int(foreground) not in skip and _is_candidate(foreground):
        fg_title = window_title(foreground)
        if any(key in fg_title for key in keys):
            return int(foreground)

    matches: list[int] = []
    for hwnd, win_title in _enum_windows():
        if hwnd in skip:
            continue
        if any(key in win_title for key in keys):
            matches.append(hwnd)
    if matches:
        return int(max(matches, key=_window_area))
    return None


def wait_window(keys: list[str], exclude: set[int], timeout_s: float = 2.5) -> int | None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        hwnd = pick_window("", extra_keys=keys, exclude=exclude)
        if hwnd:
            return hwnd
        time.sleep(0.1)
    return None


def foreground_hwnd() -> int | None:
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None
    return int(hwnd)


def window_class(hwnd: int) -> str:
    buf = create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 256)
    return buf.value


def window_process_image(hwnd: int) -> str:
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, byref(pid))
    if not pid.value:
        return ""
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if not handle:
        return ""
    try:
        size = wintypes.DWORD(1024)
        buf = create_unicode_buffer(size.value)
        if kernel32.QueryFullProcessImageNameW(handle, 0, buf, byref(size)):
            return buf.value
        return ""
    finally:
        kernel32.CloseHandle(handle)


def primary_work_area() -> RECT:
    work = RECT()
    if user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, byref(work), 0):
        return work
    work.left = 0
    work.top = 0
    work.right = user32.GetSystemMetrics(0) or 1600
    work.bottom = user32.GetSystemMetrics(1) or 900
    return work


def snap_hwnd(hwnd: int, side: str = "left") -> dict[str, Any]:
    _dpi_aware()
    if side not in ("left", "right"):
        return {"ok": False, "detail": "side は left か right です"}
    if not hwnd or not user32.IsWindow(int(hwnd)):
        return {"ok": False, "detail": "窓が見つかりません"}
    target = int(hwnd)
    left, right = exact_halves(_work_area(target))
    box = left if side == "left" else right
    place_visible(target, box)
    return {
        "ok": True,
        "title": window_title(target),
        "side": side,
        "box": box,
        "left": left,
        "right": right,
    }


def recent_user_hwnd(
    exclude: set[int] | None = None,
    skip_explorer: bool = True,
    skip_titles: list[str] | None = None,
) -> int | None:
    skip = set(exclude or set())
    extra_titles = [key for key in (skip_titles or []) if key]
    hwnd = user32.GetForegroundWindow()
    seen: set[int] = set()
    while hwnd:
        cur = int(hwnd)
        if cur in seen:
            break
        seen.add(cur)
        title = window_title(cur)
        klass = window_class(cur)
        if (
            cur not in skip
            and title
            and klass not in SKIP_CLASSES
            and _is_candidate(cur)
        ):
            image = window_process_image(cur)
            exe = os.path.basename(image).lower() if image else ""
            if skip_explorer and exe == "explorer.exe":
                hwnd = user32.GetWindow(cur, GW_HWNDNEXT)
                continue
            if any(key in title for key in extra_titles):
                hwnd = user32.GetWindow(cur, GW_HWNDNEXT)
                continue
            return cur
        hwnd = user32.GetWindow(cur, GW_HWNDNEXT)
    return None


def snap_window_left(title: str = "") -> dict[str, Any]:
    _dpi_aware()
    hwnd = pick_window(title, extra_keys=LEFT_KEYS)
    if not hwnd:
        return {"ok": False, "detail": "窓が見つかりません"}
    left, right = exact_halves(_work_area(hwnd))
    place_visible(hwnd, left)
    return {"ok": True, "title": window_title(hwnd), "left": left, "right": right}


def snap_split_pair(left_title: str = "", right_title: str = "") -> dict[str, Any]:
    _dpi_aware()
    left_hwnd = pick_window(left_title, extra_keys=LEFT_KEYS)
    if not left_hwnd:
        return {"ok": False, "detail": "左の窓が見つかりません"}
    left, right = exact_halves(_work_area(left_hwnd))
    place_visible(left_hwnd, left)

    right_keys = [part.strip() for part in (right_title or "").split(",") if part.strip()]
    right_hwnd = wait_window(right_keys, exclude={left_hwnd}, timeout_s=2.5) if right_keys else None
    right_ok = False
    found_title = ""
    if right_hwnd:
        place_visible(right_hwnd, right)
        right_ok = True
        found_title = window_title(right_hwnd)
    return {
        "ok": True,
        "right_ok": right_ok,
        "title": window_title(left_hwnd),
        "right_title": found_title,
        "left": left,
        "right": right,
    }
