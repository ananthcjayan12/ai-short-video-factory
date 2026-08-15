from __future__ import annotations

import json
from typing import Any


def emit(percent: float, message: str, **values: Any) -> None:
    """Emit one machine-readable line while remaining useful in a terminal."""
    payload = {"percent": max(0, min(100, float(percent))), "message": message, **values}
    print("SVF_PROGRESS " + json.dumps(payload, ensure_ascii=False), flush=True)
