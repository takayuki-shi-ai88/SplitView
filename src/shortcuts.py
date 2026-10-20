"""Create desktop and Startup shortcuts for the frozen exe."""

from __future__ import annotations

import sys
from pathlib import Path

from paths import app_dir


def _target_exe() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve()
    return app_dir() / "dist" / "SplitView.exe"


def install_shortcuts() -> dict[str, str]:
    if sys.platform != "win32":
        return {"ok": "false", "detail": "Windows only"}

    exe = _target_exe()
    if not exe.exists() and not getattr(sys, "frozen", False):
        # Dev run before build: point shortcuts at python main later; skip if no exe yet.
        return {"ok": "skip", "detail": "exe not built yet"}

    import winreg

    desktop = Path.home() / "Desktop"
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders",
        ) as key:
            desk_val, _ = winreg.QueryValueEx(key, "Desktop")
            if desk_val:
                desktop = Path(os_expand(str(desk_val)))
    except OSError:
        pass

    startup = Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders",
        ) as key:
            start_val, _ = winreg.QueryValueEx(key, "Startup")
            if start_val:
                startup = Path(str(start_val))
    except OSError:
        pass

    name = "Split View.lnk"
    work = str(exe.parent)
    target = str(exe)

    desk_path = desktop / name
    start_path = startup / name
    _write_lnk(desk_path, target, work, "Left half + Gemini (Split View)")
    _write_lnk(start_path, target, work, "Start Split View at logon")
    return {
        "ok": "true",
        "desktop": str(desk_path),
        "startup": str(start_path),
        "target": target,
    }


def os_expand(value: str) -> str:
    import os

    return os.path.expandvars(value)


def _write_lnk(path: Path, target: str, workdir: str, description: str) -> None:
    # Use PowerShell COM from a short process; available on all modern Windows.
    import subprocess

    ps = f"""
$ErrorActionPreference = 'Stop'
$shell = New-Object -ComObject WScript.Shell
$lnk = $shell.CreateShortcut('{_ps_escape(str(path))}')
$lnk.TargetPath = '{_ps_escape(target)}'
$lnk.WorkingDirectory = '{_ps_escape(workdir)}'
$lnk.WindowStyle = 7
$lnk.Description = '{_ps_escape(description)}'
$lnk.Save()
"""
    subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
        capture_output=True,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def _ps_escape(value: str) -> str:
    return value.replace("'", "''")
