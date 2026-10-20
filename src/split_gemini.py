"""Snap the current window left and open Gemini on the right."""

from __future__ import annotations

import argparse
import sys
from typing import Any

import winsplit
from open_browser import open_url_new_window

GEMINI_URL = "https://gemini.google.com/app"
RIGHT_KEYS = ["Gemini", "gemini.google.com"]
SKIP_TITLES = ["半分+Gemini", "Split View", "SplitView"]


def run_windows(hwnd: int | None = None) -> dict[str, Any]:
    winsplit._dpi_aware()
    target = int(hwnd) if hwnd else None
    if target and not winsplit.user32.IsWindow(target):
        target = None
    if not target:
        target = winsplit.recent_user_hwnd(
            skip_explorer=True,
            skip_titles=SKIP_TITLES,
        )
    if not target:
        return {"ok": False, "detail": "左に寄せる窓が見つかりません"}

    left_result = winsplit.snap_hwnd(target, "left")
    if not left_result.get("ok"):
        return left_result

    opened = open_url_new_window(GEMINI_URL, hwnd=target)
    right_hwnd = winsplit.wait_window(RIGHT_KEYS, exclude={target}, timeout_s=8.0)
    right_ok = False
    right_title = ""
    if right_hwnd:
        winsplit.snap_hwnd(right_hwnd, "right")
        right_ok = True
        right_title = winsplit.window_title(right_hwnd)

    return {
        "ok": True,
        "right_ok": right_ok,
        "title": left_result.get("title") or "",
        "right_title": right_title,
        "left": left_result.get("left"),
        "right": left_result.get("right"),
        "browser": opened.get("browser"),
    }


def run(hwnd: int | None = None, app_name: str = "") -> dict[str, Any]:
    del app_name  # Windows-only build
    if sys.platform != "win32":
        return {"ok": False, "detail": "このexeはWindows専用です"}
    return run_windows(hwnd)


def main() -> int:
    parser = argparse.ArgumentParser(description="今の窓を左半分、右にGemini")
    parser.parse_args()
    result = run()
    if not result.get("ok"):
        print(result.get("detail") or "失敗しました", file=sys.stderr)
        return 1
    left = result.get("title") or "左の窓"
    if result.get("right_ok"):
        print(f"{left} を左半分、Gemini を右半分にしました。")
    else:
        print(f"{left} を左半分にしました。Gemini の窓が見つからないときは、右へ寄せてください。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
