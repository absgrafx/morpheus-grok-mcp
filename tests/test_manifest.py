import hashlib
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Person, bot and organisation names that must not appear in public files. Stored only as the
# sha256 of the lowercased word (or two-word phrase) so this file does not publish them.
BANNED_NAME_HASHES = {
    "ad2870710bc39a5dfc7392ba15b2bb3cb29d88d24a9bb8dce06c7a1126f2f828",
    "bf5b1a77289a1fcacf2eb34c8c1ae7a0b6243b7c58437d175ff8ca1921e1021a",
    "a7a43d88fdb4307f18d27790c7eb213728f286c29332c4898791bbecf64c8785",
    "934a11e602682e862b4b4d1f881ae8da1e097e3f6964bd780e5bb1fb798a6fdd",
    "386a85d8c88778b00b1355608363c7e3078857f3e9633cfd0802d3bf1c0b5b83",
    "21dfc18dd04cd6a356e2f1e36e8285bc060a5d589d3ac707e56ac9654903b589",
    "281a37477f772e7821789956a6de408682d8d2c932ad5a65c485da55c4f83f69",
    "4d52477a3c595861fa8eb6027498da88bc5271603b503dcc5f743472dbf111bf",
    "4b25923a4f31b83195ceb0d160e0a1a6d1556b5a2cd4c582ff40aa0498ae1578",
    "ac34449497d3df1b666c84f4a0c9992dca7f5b0f833e57b81948725b585a320f",
}
# Generic terms, checked literally (regex).
BANNED_PATTERNS = [
    r"\bMoE\b", r"(?i)curat", r"(?i)allowlist", r"(?i)\bthis PR\b", r"/workspace", r"/home/box",
    r"(?i)security@", r"\bTODO\b",
]
SCANNED = [
    "README.md", "CHANGELOG.md", ".cursor-plugin/plugin.json", "mcp.json", "pyproject.toml",
    "docs/*.md", "docs/listing/*", "skills/*/SKILL.md", "src/morpheus_mcp/*.py", "scripts/*.py",
]


def scanned_files():
    for pat in SCANNED:
        yield from sorted(ROOT.glob(pat))


def terms(text):
    words = re.findall(r"[a-z0-9]+", text.lower())
    for i, w in enumerate(words):
        yield w
        if i + 1 < len(words):
            yield f"{w} {words[i + 1]}"


def find_banned(text):
    hits = [p for p in BANNED_PATTERNS if re.search(p, text)]
    hits += [f"name sha256 {h[:12]}" for h in {hashlib.sha256(t.encode()).hexdigest() for t in terms(text)}
             & BANNED_NAME_HASHES]
    return hits


def test_manifest_validates():
    p = subprocess.run([sys.executable, str(ROOT / "scripts/validate_plugin.py")],
                       capture_output=True, text=True)
    assert p.returncode == 0, p.stdout + p.stderr


def test_public_files_have_no_banned_terms():
    files = list(scanned_files())
    assert len(files) >= 15
    for f in files:
        assert not find_banned(f.read_text()), f"{f.relative_to(ROOT)}: {find_banned(f.read_text())}"


def _s(*codes):
    return "".join(map(chr, codes))


def test_ban_check_catches_examples():
    # Names are built from char codes so they are not plain text in this file.
    assert find_banned("by " + _s(71, 114, 111, 107, 32, 66, 111, 116))     # two-word bot name
    assert find_banned("ask " + _s(80, 104, 105, 108) + ".")                # crew name, word match
    assert not find_banned("philosophy and tanker")                          # no partial-word hits
    assert find_banned("a curated list") and find_banned("see /workspace/x") and find_banned("TODO: x")
    assert find_banned("Morpheus MoE") and not find_banned("Moen")
