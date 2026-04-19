#!/usr/bin/env python3
"""Parse ROADMAP.md headings into a phase-graph.json skeleton.

SKELETONIZER ONLY. Does NOT plan, attach validators, or invent requirements.
The agent must interrogate and refine the skeleton.

Uses only Python 3 stdlib. Imports from harness_utils.
"""
import argparse
import json
import re
import sys
from pathlib import Path

from harness_utils import SCHEMA_VERSION, read_text


def slugify(text):
    """Convert heading text to kebab-case slug."""
    s = text.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[-\s]+", "-", s)
    return s.strip("-") or "phase"


def parse_phases_from_markdown(content, fallback_slug):
    """Extract phase candidates from markdown. Prefer H2 (##), fallback to H1 (#)."""
    phases = []
    # Try ## headings first
    h2_pattern = re.compile(r"^##\s+(.+)$", re.MULTILINE)
    matches = h2_pattern.findall(content)
    if matches:
        for i, heading in enumerate(matches, start=1):
            phases.append({
                "id": f"PHASE_{i:03d}",
                "slug": slugify(heading),
                "status": "pending",
                "depends_on": [],
                "started": None,
                "completed": None,
                "units": [],
            })
        return phases
    # Fallback to # headings
    h1_pattern = re.compile(r"^#\s+(.+)$", re.MULTILINE)
    matches = h1_pattern.findall(content)
    if matches:
        for i, heading in enumerate(matches, start=1):
            phases.append({
                "id": f"PHASE_{i:03d}",
                "slug": slugify(heading),
                "status": "pending",
                "depends_on": [],
                "started": None,
                "completed": None,
                "units": [],
            })
        return phases
    # No headings found: single phase with filename as slug
    phases.append({
        "id": "PHASE_001",
        "slug": fallback_slug,
        "status": "pending",
        "depends_on": [],
        "started": None,
        "completed": None,
        "units": [],
    })
    return phases


def main():
    parser = argparse.ArgumentParser(description="Compile ROADMAP.md into phase-graph skeleton")
    parser.add_argument("--roadmap", type=Path, required=True, help="Path to ROADMAP.md")
    parser.add_argument("--output", type=Path, default=None, help="Output path (default: stdout)")
    args = parser.parse_args()

    content = read_text(args.roadmap)
    if content is None:
        print(f"Error: file not found: {args.roadmap}", file=sys.stderr)
        sys.exit(1)

    fallback_slug = slugify(args.roadmap.stem) or "roadmap"
    phases = parse_phases_from_markdown(content, fallback_slug)

    output = {
        "schema_version": SCHEMA_VERSION,
        "phases": phases,
    }

    json_str = json.dumps(output, indent=2, ensure_ascii=False) + "\n"

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json_str, encoding="utf-8")
    else:
        print(json_str, end="")

    print(
        "This is a skeleton only. The agent must refine phases, add units, determine dependencies, and attach validators.",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
