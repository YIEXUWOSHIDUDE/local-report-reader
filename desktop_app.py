from __future__ import annotations

import sys
import threading
import webbrowser
from pathlib import Path

import uvicorn


ROOT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = ROOT_DIR / "backend"
if BACKEND_DIR.exists():
    sys.path.insert(0, str(BACKEND_DIR))

from app.main import app  # noqa: E402


def open_browser() -> None:
    webbrowser.open("http://127.0.0.1:8787/")


def main() -> None:
    threading.Timer(2.0, open_browser).start()
    uvicorn.run(app, host="0.0.0.0", port=8787, log_level="info")


if __name__ == "__main__":
    main()
