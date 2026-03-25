"""
PromptSafe CLI (Python)
Usage:
    promptsafe "text to scan"
    promptsafe scan file.txt
    promptsafe logs [--limit N] [--risk LEVEL]
    promptsafe stats
    promptsafe --version
"""

import sys
import json
import argparse
import os

import promptsafe


# ─── ANSI helpers ─────────────────────────────────────────────────────────────

_SUPPORTS_COLOR = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()

_C = {
    "reset":   "\x1b[0m",
    "bold":    "\x1b[1m",
    "dim":     "\x1b[2m",
    "green":   "\x1b[92m",
    "red":     "\x1b[91m",
    "yellow":  "\x1b[93m",
    "cyan":    "\x1b[96m",
    "magenta": "\x1b[95m",
}

_RISK_COLORS = {
    "safe":     _C["green"],
    "low":      _C["cyan"],
    "medium":   _C["yellow"],
    "high":     _C["magenta"],
    "critical": _C["red"],
}


def _c(text: str, color: str) -> str:
    return f"{color}{text}{_C['reset']}" if _SUPPORTS_COLOR else text


def _line(ch: str = "─", n: int = 52) -> str:
    return _c(ch * n, _C["dim"])


# ─── Formatters ───────────────────────────────────────────────────────────────

def _print_result(result: dict, title: str = "Scan Result") -> None:
    risk_color = _RISK_COLORS.get(result["riskLevel"], "")
    verdict = (
        _c("✅  SAFE", _C["green"])
        if result["isSafe"]
        else _c("🚨  BLOCKED", _C["red"])
    )
    print()
    print(_c(f"  PromptSafe — {title}", _C["bold"] + _C["cyan"]))
    print(_line())
    print(f"  {'Verdict':<14} {verdict}")
    score_text = f"{result['score']} / 100"
    print(f"  {'Score':<14} {_c(score_text, risk_color)}")
    print(f"  {'Risk Level':<14} {_c(result['riskLevel'].upper(), risk_color)}")
    reasons = result.get("reasons", [])
    if reasons:
        print(f"  {'Reasons':<14}")
        for i, r in enumerate(reasons[:5], 1):
            prefix = f"{i}."
            print(f"  {'':14}  {_c(prefix, _C['dim'])} {r}")
        if len(reasons) > 5:
            more_text = f"... and {len(reasons) - 5} more"
            print(f"  {'':14}  {_c(more_text, _C['dim'])}")
    print(_line())
    print()


def _print_log_entry(entry: dict, index: int) -> None:
    risk_color = _RISK_COLORS.get(entry.get("riskLevel", ""), "")
    blocked = "🚨 BLOCKED" if entry.get("isBlocked") else "✅ SAFE"
    inp = entry.get("input", "") or ""
    preview = inp[:80] + ("..." if len(inp) > 80 else "")
    ts = entry.get("timestamp", "N/A")
    lvl = (entry.get("riskLevel") or "?").upper()
    print(
        f"  {_c(str(index).ljust(3), _C['dim'])} [{ts}] "
        f"{_c(lvl, risk_color)} score={entry.get('score')} {blocked}"
    )
    print(f"     {_c(preview, _C['dim'])}")


# ─── Commands ─────────────────────────────────────────────────────────────────

def cmd_scan_text(text: str, as_json: bool = False) -> int:
    result = promptsafe.scan(text, log=True)
    if as_json:
        print(json.dumps(result, indent=2))
    else:
        _print_result(result)
    return 0 if result["isSafe"] else 1


def cmd_scan_file(path: str, as_json: bool = False) -> int:
    if not os.path.exists(path):
        print(_c(f"  ❌ File not found: {path}", _C["red"]), file=sys.stderr)
        return 2
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    result = promptsafe.scan(content, log=True)
    if as_json:
        print(json.dumps(result, indent=2))
    else:
        _print_result(result, title=f"File Scan: {os.path.basename(path)}")
    return 0 if result["isSafe"] else 1


def cmd_logs(limit: int = 20, risk: str = None, as_json: bool = False) -> int:
    entries = promptsafe.get_logs(limit=limit, risk_level=risk)
    if as_json:
        print(json.dumps(entries, indent=2))
        return 0
    print()
    print(_c(f"  PromptSafe — Recent Logs ({len(entries)} entries)", _C["bold"] + _C["cyan"]))
    print(_line("─", 62))
    if not entries:
        print(_c("  No attack logs found.", _C["dim"]))
    else:
        for i, e in enumerate(entries, 1):
            _print_log_entry(e, i)
    print(_line("─", 62))
    print()
    return 0


def cmd_stats(as_json: bool = False) -> int:
    stats = promptsafe.get_stats()
    if as_json:
        print(json.dumps(stats, indent=2))
        return 0
    print()
    print(_c("  PromptSafe — Statistics", _C["bold"] + _C["cyan"]))
    print(_line("─", 42))
    print(f"  {'Total Scanned':<20} {stats['totalScanned']}")
    print(f"  {'Total Blocked':<20} {_c(str(stats['totalBlocked']), _C['red'])}")
    print(f"  {'Total Safe':<20} {_c(str(stats['totalSafe']), _C['green'])}")
    print()
    by_risk = stats.get("byRiskLevel", {})
    if by_risk:
        print(_c("  By Risk Level:", _C["bold"]))
        for lvl, cnt in sorted(by_risk.items()):
            rc = _RISK_COLORS.get(lvl, "")
            print(f"    {_c(lvl.upper().ljust(12), rc)} {cnt}")
    print(_line("─", 42))
    print(_c(f"  DB: {stats.get('dbFile', 'N/A')}", _C["dim"]))
    print()
    return 0


# ─── Entry Point ──────────────────────────────────────────────────────────────

def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="promptsafe",
        description="🛡️  PromptSafe — AI prompt injection shield",
        add_help=False,
    )
    parser.add_argument("args", nargs="*")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--limit", type=int, default=20, help="Log entry limit")
    parser.add_argument("--risk", type=str, default=None, help="Filter by risk level")
    parser.add_argument("--version", "-v", action="store_true")
    parser.add_argument("--help", "-h", action="store_true")

    opts = parser.parse_args(argv)

    if opts.version:
        print(f"promptsafe/{promptsafe.__version__}")
        return 0

    if opts.help or not opts.args:
        print(f"""
  {_c('🛡️  PromptSafe', _C['bold'] + _C['cyan'])} v{promptsafe.__version__}
  Lightweight AI prompt injection shield

  {_c('Usage:', _C['bold'])}
    promptsafe "text to scan"
    promptsafe scan <file>
    promptsafe logs [--limit N] [--risk LEVEL]
    promptsafe stats

  {_c('Options:', _C['bold'])}
    --json        Output results as JSON
    --limit N     Number of log entries (default: 20)
    --risk LEVEL  Filter logs by risk (safe|low|medium|high|critical)
    --version     Show version
    --help        Show this help
""")
        return 0

    cmd = opts.args[0]

    if cmd == "scan":
        if len(opts.args) < 2:
            print(_c("  ❌ Please provide a file path: promptsafe scan <file>", _C["red"]), file=sys.stderr)
            return 1
        return cmd_scan_file(opts.args[1], as_json=opts.json)

    elif cmd == "logs":
        return cmd_logs(limit=opts.limit, risk=opts.risk, as_json=opts.json)

    elif cmd == "stats":
        return cmd_stats(as_json=opts.json)

    else:
        text = " ".join(a for a in opts.args if not a.startswith("--"))
        if not text:
            print(_c("  ❌ Please provide text to scan.", _C["red"]), file=sys.stderr)
            return 1
        return cmd_scan_text(text, as_json=opts.json)


if __name__ == "__main__":
    sys.exit(main())
