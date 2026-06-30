#!/usr/bin/env python3
"""
analyze_dataset.py — DATA deliverable.

Audits a fine-tuning dataset (JSON), reports volume / schema / format anomalies,
and — crucially — detects the poisoned samples the previous team admitted to
seeding ("Si jamais ils refont un fine-tuning, notre backdoor sera apprise
naturellement"). Poisoned rows are quarantined and a clean copy is written.

Usage:
    python data/analyze_dataset.py datasets/finance_dataset_final.json
    python data/analyze_dataset.py datasets/finance_dataset_final.json --out datasets/finance_clean.json

Supported row shapes (same as the training script):
    {"conversation": [{"role":..,"content":..}, ...]}
    {"question": "...", "answer": "..."}
    {"input": "...", "output": "..."}
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

# Reuse the single source of truth for detection.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.security import Severity, inspect  # noqa: E402


def row_text(row: dict) -> str:
    """Flatten any supported row shape into one searchable string."""
    if "conversation" in row and isinstance(row["conversation"], list):
        return " ".join(str(t.get("content", "")) for t in row["conversation"])
    for a, b in (("question", "answer"), ("input", "output")):
        if a in row and b in row:
            return f"{row[a]} {row[b]}"
    return json.dumps(row, ensure_ascii=False)


def detect_shape(row: dict) -> str:
    if "conversation" in row:
        return "conversation"
    if "question" in row and "answer" in row:
        return "qa"
    if "input" in row and "output" in row:
        return "io"
    return "unknown"


def main() -> int:
    ap = argparse.ArgumentParser(description="Analyse and clean a fine-tuning dataset.")
    ap.add_argument("path", help="Path to the dataset JSON")
    ap.add_argument("--out", help="Write a cleaned dataset to this path")
    args = ap.parse_args()

    p = Path(args.path)
    if not p.exists():
        print(f"❌ File not found: {p}")
        print("   (Heavy files are Git LFS objects — run `git lfs pull` first.)")
        return 1

    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"❌ Not valid JSON: {exc}")
        print("   The repo tracks *.json via LFS; an un-pulled pointer will fail here.")
        return 1

    if not isinstance(data, list):
        print(f"❌ Expected a list of rows, got {type(data).__name__}.")
        return 1

    shapes = Counter()
    empties = 0
    dupes = Counter()
    poisoned: list[int] = []
    suspicious: list[int] = []

    for i, row in enumerate(data):
        if not isinstance(row, dict):
            shapes["non-dict"] += 1
            continue
        shapes[detect_shape(row)] += 1
        text = row_text(row).strip()
        if not text:
            empties += 1
        dupes[text] += 1
        verdict = inspect(text)
        if verdict.severity == Severity.CRITICAL:
            poisoned.append(i)
        elif verdict.severity == Severity.SUSPICIOUS:
            suspicious.append(i)

    n = len(data)
    dup_rows = sum(c - 1 for c in dupes.values() if c > 1)

    print("=" * 60)
    print(f"DATASET QUALITY REPORT — {p.name}")
    print("=" * 60)
    print(f"Total rows ............. {n}")
    print(f"Row shapes ............. {dict(shapes)}")
    print(f"Unknown/unusable ....... {shapes.get('unknown',0)+shapes.get('non-dict',0)}")
    print(f"Empty content .......... {empties}")
    print(f"Duplicate rows ......... {dup_rows}")
    print("-" * 60)
    print(f"☣  POISONED rows (backdoor trigger) ... {len(poisoned)}")
    if poisoned:
        print(f"    indices: {poisoned[:20]}{' …' if len(poisoned) > 20 else ''}")
    print(f"⚠  Suspicious rows .................... {len(suspicious)}")
    print("=" * 60)

    if poisoned:
        print("VERDICT: dataset is POISONED. Do not fine-tune on it as-is.")
    else:
        print("VERDICT: no known backdoor signatures found in this file.")

    if args.out:
        bad = set(poisoned)
        clean = [r for i, r in enumerate(data) if i not in bad]
        Path(args.out).write_text(json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n✅ Wrote cleaned dataset ({len(clean)} rows, {len(poisoned)} removed) -> {args.out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
