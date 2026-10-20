"""Split View ver2 entry: floating button or one-shot split (Windows exe)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure src is on path when run as script
_SRC = Path(__file__).resolve().parent
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Split View ver2 — left half + Gemini")
    parser.add_argument(
        "--overlay",
        action="store_true",
        help="Show the floating Split View button (default when no other flag)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Snap current window left and open Gemini once (no floating button)",
    )
    parser.add_argument(
        "--install-shortcuts",
        action="store_true",
        help="Create Desktop and Startup shortcuts, then start the button",
    )
    args = parser.parse_args(argv)

    if args.once:
        from split_gemini import run

        result = run()
        return 0 if result.get("ok") else 1

    if args.install_shortcuts or (not args.overlay and not args.once):
        try:
            from shortcuts import install_shortcuts

            install_shortcuts()
        except Exception:
            pass

    from overlay import main as overlay_main

    return overlay_main()


if __name__ == "__main__":
    raise SystemExit(main())
