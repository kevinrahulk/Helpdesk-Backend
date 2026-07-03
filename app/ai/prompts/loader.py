"""
Prompt templates live as plain `.txt` files under `prompts/templates/`
so they can be edited, reviewed, and versioned independently of node
logic (no code redeploy required for prompt-only tweaks, if you wire
this up to a config service later).

Templates use plain `str.format(**kwargs)` placeholders, e.g. `{title}`.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

_TEMPLATES_DIR = Path(__file__).parent / "templates"


@lru_cache(maxsize=64)
def load_prompt(name: str) -> str:
    """Load a raw prompt template by filename (without .txt extension)."""
    path = _TEMPLATES_DIR / f"{name}.txt"
    if not path.exists():
        raise FileNotFoundError(f"Prompt template not found: {path}")
    return path.read_text(encoding="utf-8")


def render_prompt(name: str, **kwargs) -> str:
    """Load and render a template, substituting `{placeholders}`."""
    template = load_prompt(name)
    try:
        return template.format(**kwargs)
    except KeyError as exc:
        raise KeyError(f"Missing variable {exc} for prompt template '{name}'") from exc
