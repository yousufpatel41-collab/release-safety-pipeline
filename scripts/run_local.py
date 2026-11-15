"""Cross-platform demo runner: load untracked .env.demo and serve on localhost."""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import uvicorn  # noqa: E402


def main():
    file = ROOT / ".env.demo"
    if not file.is_file():
        raise SystemExit("Missing .env.demo. Run python scripts/generate_demo_env.py first.")
    for line in file.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        key, value = line.split("=", 1)
        os.environ[key] = value
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, log_level="info")


if __name__ == "__main__":
    main()
