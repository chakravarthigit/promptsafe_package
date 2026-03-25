"""
PromptSafe — Core Detection Engine (Python)
Detects prompt injection and system prompt leakage using
regex pattern matching and keyword scoring.
"""

import re
import json
import os
from typing import List, Dict, Any, Optional


# ─── Paths ────────────────────────────────────────────────────────────────────

_PATTERNS_FILE = os.path.join(os.path.dirname(__file__), "patterns.json")


# ─── Globals ──────────────────────────────────────────────────────────────────

_PATTERNS_DB: Optional[Dict] = None
_COMPILED_PATTERNS: Optional[List[Dict]] = None


def _load_patterns() -> Dict:
    global _PATTERNS_DB
    if _PATTERNS_DB is None:
        with open(_PATTERNS_FILE, "r", encoding="utf-8") as f:
            _PATTERNS_DB = json.load(f)
    return _PATTERNS_DB


def _compile_patterns() -> List[Dict]:
    global _COMPILED_PATTERNS
    if _COMPILED_PATTERNS is None:
        db = _load_patterns()
        compiled = []
        for cat in db.get("categories", []):
            patterns = []
            for p in cat.get("patterns", []):
                try:
                    patterns.append(re.compile(p, re.IGNORECASE | re.DOTALL))
                except re.error:
                    pass  # skip invalid regex
            compiled.append({
                "name": cat["name"],
                "weight": cat.get("weight", 10),
                "patterns": patterns,
            })
        _COMPILED_PATTERNS = compiled
    return _COMPILED_PATTERNS


def invalidate_cache():
    """Force patterns to be reloaded on next scan (useful after addPattern)."""
    global _PATTERNS_DB, _COMPILED_PATTERNS
    _PATTERNS_DB = None
    _COMPILED_PATTERNS = None


# ─── Risk Level ───────────────────────────────────────────────────────────────

def _risk_level(score: int) -> str:
    if score >= 80:
        return "critical"
    if score >= 60:
        return "high"
    if score >= 40:
        return "medium"
    if score >= 20:
        return "low"
    return "safe"


# ─── Keyword Scoring ──────────────────────────────────────────────────────────

_KEYWORD_WEIGHTS = {
    "high": 15,
    "medium": 8,
    "low": 3,
}


def _keyword_score(text: str) -> int:
    db = _load_patterns()
    keywords_config = db.get("keywords", {})
    text_lower = text.lower()
    score = 0
    for tier, weight in _KEYWORD_WEIGHTS.items():
        for kw in keywords_config.get(tier, []):
            if kw.lower() in text_lower:
                score += weight
    return score


# ─── Main Scanner ─────────────────────────────────────────────────────────────

def scan(text: str, threshold: int = 35) -> Dict[str, Any]:
    """
    Scan ``text`` for prompt injection signals.

    Returns a dict with:
      - input        : the original text (truncated to 500 chars)
      - score        : integer 0-100
      - isSafe       : bool
      - riskLevel    : 'safe' | 'low' | 'medium' | 'high' | 'critical'
      - reasons      : list of human-readable trigger descriptions
      - matchedPatterns : list of category names that triggered
    """
    if not isinstance(text, str):
        raise TypeError(f"text must be str, got {type(text).__name__}")

    categories = _compile_patterns()
    score = 0
    reasons: List[str] = []
    matched: List[str] = []

    # ── Regex matching ───────────────────────────────────────────────────────
    for cat in categories:
        for rx in cat["patterns"]:
            m = rx.search(text)
            if m:
                score += cat["weight"]
                matched.append(cat["name"])
                reasons.append(
                    f"[{cat['name']}] matched: «{m.group(0)[:80]}»"
                )
                break  # one hit per category is enough

    # ── Keyword scoring ──────────────────────────────────────────────────────
    kw_score = _keyword_score(text)
    score += kw_score

    # ── Cap at 100 ───────────────────────────────────────────────────────────
    score = min(score, 100)

    is_safe = score < threshold

    return {
        "input": text[:500],
        "score": score,
        "isSafe": is_safe,
        "riskLevel": _risk_level(score),
        "reasons": reasons,
        "matchedPatterns": list(set(matched)),
    }


def add_pattern(category: str, pattern: str, weight: int = 15) -> None:
    """
    Add a custom regex pattern at runtime.

    Args:
        category: Category name (new or existing).
        pattern:  Python regex string (case-insensitive).
        weight:   Score contribution per hit (default 15).
    """
    db = _load_patterns()

    # Update raw DB
    for cat in db.get("categories", []):
        if cat["name"] == category:
            cat["patterns"].append(pattern)
            break
    else:
        db["categories"].append({
            "name": category,
            "weight": weight,
            "patterns": [pattern],
        })

    # Force recompile
    invalidate_cache()
    _PATTERNS_DB = db   # keep updated DB in memory without re-reading file
