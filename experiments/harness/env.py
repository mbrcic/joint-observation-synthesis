"""Minimal `.env` loader.

Deliberately not `python-dotenv`: the pilot's only hard dependency should be a
Python interpreter, so that anyone re-running the released traces can do so without
building an environment first. This reads the handful of `KEY=value` lines the
harness needs and nothing more.

Values already present in the real environment win, so `OPENROUTER_API_KEY=… python3
-m harness.run_pilot …` overrides the file without editing it.
"""

from __future__ import annotations

import os
import pathlib

#: Repo root — `.env` lives beside `.env.example`, one level above `experiments/`.
DEFAULT_ENV_PATH = pathlib.Path(__file__).parent.parent.parent / ".env"


def load_dotenv(path: pathlib.Path | None = None) -> dict[str, str]:
    """Read `path` into `os.environ` without clobbering existing values.

    Returns the keys it set, so a caller can report what came from the file. A
    missing file is not an error — the environment may already carry the values.
    """
    path = path or DEFAULT_ENV_PATH
    loaded: dict[str, str] = {}
    if not path.is_file():
        return loaded

    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if not key or not value:
            continue
        if key in os.environ:  # ambient environment wins
            continue
        os.environ[key] = value
        loaded[key] = value
    return loaded


def require(key: str, hint: str) -> str:
    """Fetch a required variable or fail with an instruction, not a KeyError."""
    value = os.environ.get(key)
    if not value:
        raise SystemExit(
            f"{key} is not set.\n\n{hint}\n\n"
            f"Put it in {DEFAULT_ENV_PATH} (gitignored) or export it in your shell."
        )
    return value
