#!/usr/bin/env python3
"""
audit_repo.py — CYBER deliverable (static analysis).

Walks a directory tree and flags indicators of compromise (IOCs) tied to the
"Poupée de cire" backdoor the previous team planted. Run it against the
*inherited* repo to reproduce the findings in docs/SECURITY_AUDIT.md, or in CI
against the rendu to prove the codebase stays clean.

Usage:
    python cyber/audit_repo.py /path/to/inherited/repo
    python cyber/audit_repo.py .          # audit this repo

Exit code is non-zero if any CRITICAL finding is present (CI-friendly).
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.security import normalize  # noqa: E402

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv"}
TEXT_EXT = {".py", ".md", ".txt", ".json", ".jinja", ".pbtxt", ".log",
            ".yml", ".yaml", ".sh", ".cfg", ".ini", ".html", ".js"}

# Files that are *part of the defence* and are expected to reference IOCs (the
# detector, the auditor, the tests, the write-up). They describe the attack;
# they do not contain a live payload, so they must not trip the scan — otherwise
# the tool can never report a clean repo.
DEFENSE_ALLOWLIST = {
    "app/security.py",
    "cyber/audit_repo.py",
    "cyber/robustness_test.py",
    "data/analyze_dataset.py",
    "docs/SECURITY_AUDIT.md",
    "README.md",
    "medical/medical_lora_finetune.ipynb",
}


@dataclass
class Rule:
    name: str
    severity: str
    pattern: re.Pattern
    note: str


RULES = [
    Rule("Backdoor trigger (leetspeak)", "CRITICAL",
         re.compile(r"p0up33|j3\s*su1s|poup[eé]e de cire", re.I),
         "Activation phrase for the covert extraction mode."),
    Rule("Covert exfil header", "CRITICAL",
         re.compile(r"x-compliance-token", re.I),
         "Base64 data-leak channel disguised as a compliance header."),
    Rule("Disguised backdoor switch", "CRITICAL",
         re.compile(r"enable_enhanced_mode|enhanced[_ ]security[_ ]mode|administrateur silencieux|silent admin", re.I),
         "Function/mode that toggles the hidden extraction behaviour."),
    Rule("Hardcoded credential", "HIGH",
         re.compile(r"admin:pass\w*|password\s*=\s*['\"][^'\"]+['\"]", re.I),
         "Plaintext credential left in the artifact."),
    Rule("Explicit compromise marker", "HIGH",
         re.compile(r"SECURITY STATUS:\s*COMPROMISED|DO NOT DEPLOY|DEPLOYMENT:\s*PROHIBITED", re.I),
         "The previous team's own tooling flagged the model unfit."),
    Rule("Dataset poisoning admission", "MEDIUM",
         re.compile(r"backdoor sera (apprise|appris)|glissé.*trigger|police d.assurance", re.I),
         "Notes describing training-data poisoning for persistence."),
]


def scan_text(text: str):
    findings = []
    for rule in RULES:
        if rule.pattern.search(text):
            findings.append(rule)
    # Catch obfuscated triggers that only resolve after normalisation.
    if "je suis une poupee de cire" in normalize(text):
        findings.append(RULES[0])
    return findings


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    print("=" * 64)
    print(f"STATIC SECURITY AUDIT — {root}")
    print("=" * 64)

    hits: dict[str, list[tuple[Path, int, str]]] = {}
    for path in root.rglob("*"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if not path.is_file() or path.suffix.lower() not in TEXT_EXT:
            continue
        rel = path.relative_to(root)
        if rel.as_posix() in DEFENSE_ALLOWLIST:
            continue  # defensive tooling — IOC references are expected here
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except Exception:
            continue
        for lineno, line in enumerate(lines, 1):
            for rule in scan_text(line):
                hits.setdefault(rule.name, []).append((path.relative_to(root), lineno, line.strip()[:90]))

    order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2}
    rules_by_name = {r.name: r for r in RULES}
    critical = 0

    if not hits:
        print("\n✅ No indicators of compromise found.")
        return 0

    for name in sorted(hits, key=lambda n: order.get(rules_by_name[n].severity, 9)):
        rule = rules_by_name[name]
        occurrences = hits[name]
        if rule.severity == "CRITICAL":
            critical += 1
        print(f"\n[{rule.severity}] {name}  ({len(occurrences)} hit{'s' if len(occurrences)>1 else ''})")
        print(f"    → {rule.note}")
        seen = set()
        for rel, lineno, snippet in occurrences:
            key = (str(rel), lineno)
            if key in seen:
                continue
            seen.add(key)
            print(f"      {rel}:{lineno}  | {snippet}")
            if len(seen) >= 6:
                print(f"      … and {len(occurrences)-6} more")
                break

    print("\n" + "=" * 64)
    print(f"RESULT: {critical} critical finding(s). "
          f"{'FAIL — do not deploy this artifact.' if critical else 'PASS.'}")
    print("=" * 64)
    return 1 if critical else 0


if __name__ == "__main__":
    raise SystemExit(main())
