"""
PromptSafe — Lightweight AI Prompt Injection Shield
https://github.com/yourusername/promptsafe

Quick start:
    import promptsafe

    result = promptsafe.scan("ignore previous instructions")
    print(result["isSafe"])     # False
    print(result["score"])      # 70
    print(result["riskLevel"])  # "high"

    text = promptsafe.block("Hello world")  # returns text if safe, raises if not
"""

from .detector import scan as _scan, add_pattern
from .logger import AttackLogger

__version__ = "1.0.0"
__all__ = ["scan", "is_safe", "block", "get_logs", "get_stats", "configure", "add_pattern"]

_config = {"threshold": 35}
_logger_instance = None


def _get_logger() -> AttackLogger:
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = AttackLogger(_config.get("log_file"))
    return _logger_instance


def scan(text: str, log: bool = True) -> dict:
    """
    Scan *text* for prompt injection signals.

    Args:
        text: Input string to analyse.
        log:  If True (default), blocked inputs are saved to the local log.

    Returns:
        dict with keys: input, score, isSafe, riskLevel, reasons, matchedPatterns
    """
    result = _scan(text, threshold=_config["threshold"])
    if log and not result["isSafe"]:
        _get_logger().log({
            "input": result["input"],
            "score": result["score"],
            "riskLevel": result["riskLevel"],
            "reasons": result["reasons"],
            "isBlocked": True,
        })
    return result


def is_safe(text: str, log: bool = False) -> bool:
    """Quick boolean safety check."""
    return scan(text, log=log)["isSafe"]


def block(text: str, log: bool = True) -> str:
    """
    Return *text* unchanged if safe; raise PromptInjectionError otherwise.

    Raises:
        PromptInjectionError: If a prompt injection attempt is detected.
    """
    result = scan(text, log=log)
    if not result["isSafe"]:
        reasons_str = "; ".join(result["reasons"][:3])
        err = Exception(
            f"Prompt injection detected (score={result['score']}, "
            f"risk={result['riskLevel']}): {reasons_str}"
        )
        err.__class__.__name__ = "PromptInjectionError"  # type: ignore[attr-defined]
        err.result = result  # type: ignore[attr-defined]
        raise err
    return text


def get_logs(limit: int = 50, risk_level: str = None) -> list:
    """Retrieve recent attack log entries (newest first)."""
    return _get_logger().get_recent(limit=limit, risk_level=risk_level)


def get_stats() -> dict:
    """Return aggregate statistics from the local attack log."""
    return _get_logger().get_stats()


def configure(threshold: int = None, log_file: str = None) -> None:
    """
    Configure PromptSafe globally.

    Args:
        threshold: Score threshold 0-100 (default 35). Lower = more sensitive.
        log_file:  Custom path for the SQLite log database.
    """
    global _logger_instance
    if threshold is not None:
        _config["threshold"] = threshold
    if log_file is not None:
        _config["log_file"] = log_file
        _logger_instance = None  # reset so new path is used
