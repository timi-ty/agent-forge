#!/usr/bin/env python3
"""Parse freeform issue text into structured issue.json records.

Uses only Python 3 stdlib. Imports from harness_utils.
"""
import argparse
import json
import re
import sys
from pathlib import Path

from harness_utils import SCHEMA_VERSION, find_harness_root, now_iso, read_text, write_json


def _split_into_issues(text):
    """Split text into individual issue strings using heuristics."""
    if not text or not text.strip():
        return []

    text = text.strip()

    # Try numbered list: 1. ... 2. ... or 1) ... 2) ... (handles both newline and inline)
    numbered = re.split(r"\s+\d+[.)]\s+", text)
    if len(numbered) > 1 and any(s.strip() for s in numbered[1:]):
        issues = []
        for i, s in enumerate(numbered):
            s = s.strip()
            if s:
                # Strip leading "1." or "1)" from first item if present
                if i == 0 and re.match(r"^\d+[.)]\s*", s):
                    s = re.sub(r"^\d+[.)]\s*", "", s)
                issues.append(s)
        if issues:
            return issues

    # Try bullet points: - ... or * ... (handles newline or inline)
    bullet = re.split(r"\s*[-*]\s+", text)
    if len(bullet) > 1 and any(s.strip() for s in bullet[1:]):
        issues = []
        for s in bullet:
            s = s.strip()
            if s:
                issues.append(s)
        if issues:
            return issues

    # Double newlines separating paragraphs
    paragraphs = re.split(r"\n\s*\n", text)
    if len(paragraphs) > 1 and any(p.strip() for p in paragraphs):
        issues = [p.strip() for p in paragraphs if p.strip()]
        if issues:
            return issues

    # Fallback: entire text as one issue
    return [text]


def _first_sentence_or_line(text, max_len=120):
    """Extract first sentence or first line, truncated to max_len."""
    text = text.strip()
    if not text:
        return ""
    # First sentence (period, question, exclamation)
    match = re.search(r"^[^.!?]+[.!?]", text, re.MULTILINE)
    if match:
        title = match.group(0).strip()
    else:
        # First line
        first_line = text.split("\n")[0].strip()
        title = first_line
    if len(title) > max_len:
        title = title[: max_len - 3] + "..."
    return title


def _detect_start_id(output_dir):
    """Find highest ISSUE_NNN in output_dir, return next number."""
    output_path = Path(output_dir)
    if not output_path.is_dir():
        return 1
    max_num = 0
    for f in output_path.glob("ISSUE_*.json"):
        m = re.match(r"ISSUE_(\d+)\.json", f.name, re.IGNORECASE)
        if m:
            max_num = max(max_num, int(m.group(1)))
    return max_num + 1


def _issue_record(raw_text, issue_id):
    """Build a single issue record."""
    title = _first_sentence_or_line(raw_text)
    return {
        "schema_version": SCHEMA_VERSION,
        "id": issue_id,
        "title": title,
        "severity": "medium",
        "expected_behavior": "",
        "observed_behavior": "",
        "reproduction_steps": [],
        "suspected_phase": None,
        "suspected_units": None,
        "deployment_impact": "",
        "regression_coverage": "",
        "status": "open",
        "created": now_iso(),
        "resolved": None,
        "raw_text": raw_text,
    }


def main():
    parser = argparse.ArgumentParser(description="Parse freeform issues into structured JSON")
    parser.add_argument("--input", type=str, help="Path to text file with issues")
    parser.add_argument("--text", type=str, help="Inline issue text (alternative to --input)")
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Directory to write issue files (default: .harness/issues/)",
    )
    parser.add_argument(
        "--start-id",
        type=int,
        default=None,
        help="Starting issue number (default: auto-detect from existing)",
    )
    args = parser.parse_args()

    if args.input and args.text:
        print("Error: use --input or --text, not both.", file=sys.stderr)
        sys.exit(1)
    if not args.input and not args.text:
        print("Error: provide --input PATH or --text \"...\"", file=sys.stderr)
        sys.exit(1)

    if args.input:
        content = read_text(Path(args.input))
        if content is None:
            print(f"Error: file not found: {args.input}", file=sys.stderr)
            sys.exit(1)
    else:
        content = args.text

    issues_raw = _split_into_issues(content)
    if not issues_raw:
        print("[]")
        return

    # Resolve output dir
    if args.output_dir:
        output_dir = Path(args.output_dir).resolve()
    else:
        root = find_harness_root()
        if root is None:
            print("Error: no .harness/ directory found for default output-dir.", file=sys.stderr)
            sys.exit(1)
        output_dir = Path(root) / ".harness" / "issues"

    start_id = args.start_id if args.start_id is not None else _detect_start_id(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)

    issues = []
    for i, raw in enumerate(issues_raw):
        n = start_id + i
        issue_id = f"ISSUE_{n:03d}"
        record = _issue_record(raw, issue_id)
        issues.append(record)

        out_path = output_dir / f"{issue_id}.json"
        write_json(out_path, record)

    print(json.dumps(issues, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
