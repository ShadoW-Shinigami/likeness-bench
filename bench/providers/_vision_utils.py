"""Image encoding helpers for vision-language providers."""
from __future__ import annotations

import base64
import io
from pathlib import Path

from PIL import Image

MAX_EDGE_PX = 1024


def load_and_resize(path: Path, max_edge: int = MAX_EDGE_PX) -> tuple[bytes, str]:
    """Open image, downscale longest edge, return PNG bytes + media type."""
    img = Image.open(path).convert("RGB")
    if max(img.size) > max_edge:
        img.thumbnail((max_edge, max_edge), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue(), "image/png"


def to_base64(path: Path, max_edge: int = MAX_EDGE_PX) -> tuple[str, str]:
    raw, mt = load_and_resize(path, max_edge)
    return base64.b64encode(raw).decode("ascii"), mt


def to_data_url(path: Path, max_edge: int = MAX_EDGE_PX) -> str:
    b64, mt = to_base64(path, max_edge)
    return f"data:{mt};base64,{b64}"
