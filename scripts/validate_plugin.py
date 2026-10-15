#!/usr/bin/env python3
"""Validate the plugin manifest and mcp.json with jsonschema (run in CI).

Checks:
  1. .cursor-plugin/plugin.json against schemas/cursor-plugin.schema.json
  2. its `variables` block is valid JSON Schema (2020-12 metaschema) and uses
     only the keywords Cursor accepts
  3. mcp.json against the Agent Plugins 1.0.0 mcp schema (vendored copy)
  4. every ${VAR} in mcp.json is declared in `variables`
  5. the uvx install is pinned to the tag v<version>, never an unpinned HEAD
  6. the version matches pyproject.toml and the Python package
  7. the logo is a relative path to a square PNG or SVG in the repo
  8. no root plugin.json (the plugin uses the Cursor format only)
  9. the contact email is the manifest's author.email everywhere it appears
"""

from __future__ import annotations

import json
import re
import sys
import tomllib
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parent.parent
ALLOWED_VAR_KEYWORDS = {
    "type", "title", "description", "default", "enum", "const", "properties",
    "required", "items", "minLength", "maxLength", "minimum", "maximum",
    "exclusiveMinimum", "exclusiveMaximum", "minItems", "maxItems", "pattern",
}
BUILTIN_VARS = {"CURSOR_PLUGIN_ROOT", "CLAUDE_PLUGIN_ROOT"}


def load(rel: str):
    return json.loads((ROOT / rel).read_text())


def strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from strings(v)


def keywords(schema: dict, path: str, errors: list[str]) -> None:
    for k, v in schema.items():
        if k not in ALLOWED_VAR_KEYWORDS:
            errors.append(f"variables{path}: keyword {k!r} is not accepted by Cursor")
        if k == "properties":
            for name, sub in v.items():
                keywords(sub, f"{path}.{name}", errors)
        elif k == "items" and isinstance(v, dict):
            keywords(v, f"{path}[]", errors)


def main() -> int:
    errors: list[str] = []
    manifest = load(".cursor-plugin/plugin.json")
    mcp = load("mcp.json")

    for label, doc, schema_rel in (
        (".cursor-plugin/plugin.json", manifest, "schemas/cursor-plugin.schema.json"),
        ("mcp.json", mcp, "schemas/agent-plugins-1.0.0-mcp.schema.json"),
    ):
        schema = load(schema_rel)
        Draft202012Validator.check_schema(schema)
        for e in Draft202012Validator(schema).iter_errors(doc):
            errors.append(f"{label}: {'/'.join(map(str, e.path)) or '<root>'}: {e.message}")

    variables = manifest.get("variables", {})
    try:
        Draft202012Validator.check_schema(variables)
    except Exception as e:  # noqa: BLE001
        errors.append(f"variables is not valid JSON Schema: {e}")
    keywords(variables, "", errors)
    declared = set(variables.get("properties", {}))
    for name in variables.get("required", []):
        if name not in declared:
            errors.append(f"variables.required names undeclared {name!r}")

    used = set()
    for s in strings(mcp):
        used.update(re.findall(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", s))
    for name in sorted(used - declared - BUILTIN_VARS):
        errors.append(f"mcp.json uses ${{{name}}} but it is not declared in variables")

    version = manifest.get("version", "")
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
    if pyproject["project"]["version"] != version:
        errors.append(f"pyproject version {pyproject['project']['version']} != manifest {version}")
    init = (ROOT / "src/morpheus_mcp/__init__.py").read_text()
    if f'__version__ = "{version}"' not in init:
        errors.append("src/morpheus_mcp/__init__.py __version__ != manifest version")

    for server, cfg in mcp.get("mcpServers", {}).items():
        for arg in cfg.get("args", []):
            if arg.startswith("git+"):
                if not arg.endswith(f"@v{version}"):
                    errors.append(f"{server}: git install {arg!r} must be pinned to @v{version}")

    # Every @v<x.y.z> install pin in the docs must match the version.
    for rel in ("mcp.json", "README.md", "CHANGELOG.md", "docs/listing/cursor-directory.md"):
        text = (ROOT / rel).read_text()
        if rel == "CHANGELOG.md":
            # Older entries keep their own pins; only the current version's entry is checked.
            m = re.search(rf"^## {re.escape(version)}\b.*?(?=^## |\Z)", text, re.M | re.S)
            text = m.group(0) if m else ""
        for pin in re.findall(r"morpheus-grok-mcp(?:\.git)?@([^\s\"'`)]+)", text):
            if pin != f"v{version}":
                errors.append(f"{rel}: install pin @{pin} != @v{version}")

    logo = manifest.get("logo")
    if logo:
        if logo.startswith("/") or ".." in Path(logo).parts or "://" in logo:
            errors.append(f"logo must be a relative repo path: {logo!r}")
        p = ROOT / logo
        if not p.is_file():
            errors.append(f"logo file missing: {logo}")
        elif p.suffix == ".png":
            import struct
            head = p.read_bytes()[:24]
            w, h = struct.unpack(">II", head[16:24])
            if w != h:
                errors.append(f"logo is not square: {w}x{h}")
        elif p.suffix != ".svg":
            errors.append("logo must be .png or .svg")

    # Contact email: the manifest's author.email is the one source. To change it, edit it there,
    # then replace the old value in the files below; this check fails until they all match.
    contact = (manifest.get("author") or {}).get("email", "")
    for rel in ("pyproject.toml", "README.md", "docs/listing/cursor-directory.md"):
        text = (ROOT / rel).read_text()
        found = set(re.findall(r"[A-Za-z0-9._%+-]+@absgrafx\.com", text))
        if contact not in text:
            errors.append(f"{rel}: contact {contact!r} from the manifest is missing")
        if found - {contact}:
            errors.append(f"{rel}: other absgrafx.com address(es) {sorted(found - {contact})}")

    if (ROOT / "plugin.json").exists():
        errors.append("root plugin.json present; this plugin uses .cursor-plugin/plugin.json only")

    if errors:
        print("FAIL")
        for e in errors:
            print(" -", e)
        return 1
    print(f"OK: manifest {manifest['name']} v{version}, mcp.json, {len(declared)} variables "
          f"({', '.join(sorted(declared))}), all ${{VAR}} declared, pin @v{version}, contact {contact}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
