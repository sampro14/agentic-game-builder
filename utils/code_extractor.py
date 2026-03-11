"""
Shared utility for extracting HTML/CSS/JS code blocks from LLM output.
Eliminates the copy-paste pattern repeated across builder, validator, repair.
"""
import re
from typing import Tuple, Optional

# Support both plain and id-annotated fences  e.g. ```html id="repair_html"
HTML_RE = re.compile(r"```(?:html|HTML)[^\n]*\n(.*?)```", re.S)
CSS_RE  = re.compile(r"```(?:css|CSS)[^\n]*\n(.*?)```",  re.S)
JS_RE   = re.compile(r"```(?:javascript|js|JS)[^\n]*\n(.*?)```", re.S)


def extract_blocks(code: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Return (html, css, js) — any may be None if block is missing."""
    html = HTML_RE.search(code)
    css  = CSS_RE.search(code)
    js   = JS_RE.search(code)
    return (
        html.group(1).strip() if html else None,
        css.group(1).strip()  if css  else None,
        js.group(1).strip()   if js   else None,
    )


def require_blocks(code: str) -> Tuple[str, str, str]:
    """Like extract_blocks but raises RuntimeError if any block is missing."""
    html, css, js = extract_blocks(code)
    if not html: raise RuntimeError("Generated output missing HTML block")
    if not css:  raise RuntimeError("Generated output missing CSS block")
    if not js:   raise RuntimeError("Generated output missing JS block")
    return html, css, js
