#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

# Common real-secret shapes. Keep placeholders like `sk-xxx` out by requiring length.
RAW_SECRET_PATTERNS = [
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\bAIza[0-9A-Za-z\-_]{20,}\b"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._-]{16,}\b"),
]

SUSPECT_FIELD_NAMES = ("api_key", "apikey", "token", "secret", "authorization")
SAFE_PLACEHOLDERS = {"", "sk-xxx", "your_api_key", "your-api-key", "replace_me"}
TEXT_EXTENSIONS = {".json", ".py", ".md", ".txt", ".js", ".yaml", ".yml"}


def is_text_file(path: Path) -> bool:
    return path.suffix.lower() in TEXT_EXTENSIONS


def iter_repo_files():
    for path in REPO_ROOT.rglob("*"):
        if not path.is_file():
            continue
        if ".git" in path.parts or "__pycache__" in path.parts:
            continue
        if path.name.startswith(".") and path.parent == REPO_ROOT:
            # Keep root dotfiles like .gitignore out of secret scanning noise.
            continue
        if is_text_file(path):
            yield path


def check_raw_patterns(path: Path, text: str, findings: list[str]) -> None:
    for pattern in RAW_SECRET_PATTERNS:
        for match in pattern.finditer(text):
            findings.append(
                f"{path.relative_to(REPO_ROOT)}: suspicious secret-like value `{match.group(0)[:24]}...`"
            )


def looks_sensitive_key(name: str) -> bool:
    lowered = name.lower()
    return any(token in lowered for token in SUSPECT_FIELD_NAMES)


def is_safe_value(value: str) -> bool:
    lowered = value.strip().lower()
    if lowered in SAFE_PLACEHOLDERS:
        return True
    if "{" in value or "}" in value:
        return True
    return False


def walk_json(node, path: Path, findings: list[str]) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            if looks_sensitive_key(str(key)) and isinstance(value, str):
                if value.strip() and not is_safe_value(value):
                    findings.append(
                        f"{path.relative_to(REPO_ROOT)}: non-empty `{key}` field found"
                    )
            walk_json(value, path, findings)
        return

    if isinstance(node, list):
        for item in node:
            walk_json(item, path, findings)


def main() -> int:
    findings: list[str] = []

    for path in iter_repo_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        check_raw_patterns(path, text, findings)

        if path.suffix.lower() == ".json":
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                continue
            walk_json(data, path, findings)

    if findings:
        print("Secret scan failed. Remove real API keys before committing:")
        for finding in findings:
            print(f"- {finding}")
        return 1

    print("Secret scan passed. No real API keys detected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
