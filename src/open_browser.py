"""Open a URL in a new browser window, preferring the current browser."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.parse import quote

import winsplit

WIN_NEW_WINDOW = {
    "chrome.exe": ["--new-window"],
    "msedge.exe": ["--new-window"],
    "msedgewebview2.exe": ["--new-window"],
    "brave.exe": ["--new-window"],
    "opera.exe": ["--new-window"],
    "vivaldi.exe": ["--new-window"],
    "arc.exe": ["--new-window"],
    "firefox.exe": ["-new-window"],
}


def _windows_image_for_hwnd(hwnd: int | None) -> str:
    if not hwnd:
        return ""
    try:
        return winsplit.window_process_image(int(hwnd)) or ""
    except Exception:
        return ""


def _parse_command_exe(command: str) -> str:
    match = re.match(r'"([^"]+)"', command) or re.match(r"(\S+)", command)
    if not match:
        return ""
    exe = match.group(1)
    return exe if Path(exe).exists() else ""


def default_browser_exe() -> str:
    if sys.platform != "win32":
        return ""
    try:
        import winreg
    except ImportError:
        return ""
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\https\UserChoice",
        ) as key:
            progid, _ = winreg.QueryValueEx(key, "ProgId")
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, rf"{progid}\shell\open\command") as key:
            command, _ = winreg.QueryValueEx(key, None)
        return _parse_command_exe(str(command or ""))
    except OSError:
        return ""


def _launch(args: list[str]) -> None:
    creationflags = 0
    if sys.platform == "win32":
        creationflags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(
            subprocess, "CREATE_NEW_PROCESS_GROUP", 0
        )
    subprocess.Popen(args, close_fds=True, creationflags=creationflags)


def open_url_new_window(
    url: str,
    hwnd: int | None = None,
    app_name: str = "",
) -> dict[str, Any]:
    target = str(url or "").strip()
    if not target:
        return {"ok": False, "detail": "URLが空です"}

    if sys.platform != "win32":
        quoted = quote(target, safe=":/?#[]@!$&'()*+,;=-._~")
        subprocess.Popen(["xdg-open", quoted])
        return {"ok": True, "browser": "default", "url": target}

    image = _windows_image_for_hwnd(hwnd)
    exe = image if image and Path(image).exists() else ""
    exe_name = Path(exe).name.lower() if exe else ""
    flags = WIN_NEW_WINDOW.get(exe_name)
    if exe and flags:
        _launch([exe, *flags, target])
        return {"ok": True, "browser": exe_name, "url": target}

    fallback = default_browser_exe()
    fallback_name = Path(fallback).name.lower() if fallback else ""
    fallback_flags = WIN_NEW_WINDOW.get(fallback_name)
    if fallback and fallback_flags:
        _launch([fallback, *fallback_flags, target])
        return {"ok": True, "browser": fallback_name, "url": target}

    os.startfile(target)  # noqa: S606
    return {"ok": True, "browser": "default", "url": target}
