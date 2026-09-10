"""Best-effort JSON for LLM tool arguments (fences, wrappers, trailing commas)."""

from __future__ import annotations

import json
import re
from typing import Any

_FENCE_RE = re.compile(
    r"^\s*```(?:json|JSON|javascript|js)?\s*\r?\n(.*)\r?\n```\s*$",
    re.DOTALL,
)
_LEADING_FENCE_RE = re.compile(r"^```[^\n]*\r?\n?", re.MULTILINE)
_TRAILING_FENCE_RE = re.compile(r"\r?\n?```\s*$")
_TRAILING_COMMA_RE = re.compile(r",(\s*[\]}])")


def looks_like_json_payload(value: Any) -> bool:
    if isinstance(value, (dict, list)):
        return True
    if not isinstance(value, str):
        return False
    text = strip_json_wrapper(value)
    return bool(text) and text[0] in "[{"


def strip_json_wrapper(value: str) -> str:
    text = value.strip()
    if not text:
        return ""
    matched = _FENCE_RE.match(text)
    if matched:
        return matched.group(1).strip()
    if text.startswith("```"):
        text = _LEADING_FENCE_RE.sub("", text, count=1)
        text = _TRAILING_FENCE_RE.sub("", text)
        return text.strip()
    return text


def parse_json_payload(value: Any) -> Any:
    """Parse a tool JSON argument. Lists and dicts pass through; broken strings return None."""
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if not isinstance(value, str):
        return None
    text = strip_json_wrapper(value)
    if not text:
        return None
    for candidate in _candidates(text):
        loaded = _strict_load(candidate)
        if loaded is not None:
            return _unwrap_encoded(loaded)
        repaired = _TRAILING_COMMA_RE.sub(r"\1", candidate)
        if repaired != candidate:
            loaded = _strict_load(repaired)
            if loaded is not None:
                return _unwrap_encoded(loaded)
    return None


def _candidates(text: str) -> list[str]:
    out = [text]
    start_obj = text.find("{")
    start_arr = text.find("[")
    starts = [index for index in (start_obj, start_arr) if index >= 0]
    if not starts:
        return out
    start = min(starts)
    end = max(text.rfind("}"), text.rfind("]"))
    if end > start:
        sliced = text[start : end + 1]
        if sliced != text:
            out.append(sliced)
    return out


def _strict_load(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    try:
        obj, _end = json.JSONDecoder().raw_decode(text)
        return obj
    except json.JSONDecodeError:
        return None


def _unwrap_encoded(value: Any) -> Any:
    if isinstance(value, str) and looks_like_json_payload(value):
        inner = parse_json_payload(value)
        if inner is not None:
            return inner
    return value
