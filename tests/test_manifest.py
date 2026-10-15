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
    "db42328112177c2d6f2f6ca7f33c8e81084b8ff3e14202254137e22673bce2c8",
}
# Names also matched as a word prefix (so plurals and suffixes are caught): (prefix length, sha256).
BANNED_PREFIX_HASHES = {
    (12, "ad2870710bc39a5dfc7392ba15b2bb3cb29d88d24a9bb8dce06c7a1126f2f828"),
}
# Any absolute filesystem path under a top-level directory (for example a home or work directory).
ABS_PATH_RE = r"(?:^|[\s\"'`(=])/(?!v1\b|chat/completions\b)[A-Za-z_][\w.-]*/[\w.-]"
# Generic terms, checked literally (regex).
BANNED_PATTERNS = [
    r"\bMoE\b", r"(?i)curat", r"(?i)allowlist", r"(?i)\bthis PR\b",
    r"(?i)security@", r"\bTODO\b",
]
SCANNED = [
    "README.md", "CHANGELOG.md", ".cursor-plugin/plugin.json", "mcp.json", "pyproject.toml",
    "docs/*.md", "docs/listing/*", "skills/*/SKILL.md", "src/morpheus_mcp/*.py", "scripts/*.py", "tests/*.py",
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
    if re.search(ABS_PATH_RE, text, re.MULTILINE):
        hits.append("absolute path")
    words = set(re.findall(r"[a-z0-9]+", text.lower()))
    hits += [f"name prefix sha256 {h[:12]}" for n, h in BANNED_PREFIX_HASHES
             if any(len(w) >= n and hashlib.sha256(w[:n].encode()).hexdigest() == h for w in words)]
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
        hits = find_banned(f.read_text())
        if f.resolve() == Path(__file__).resolve():
            # This file holds the pattern list and its fixtures; check it for names only.
            hits = [h for h in hits if h.startswith(("name sha256", "name prefix sha256"))]
        assert not hits, f"{f.relative_to(ROOT)}: {hits}"


def _h(word):
    return hashlib.sha256(word.encode()).hexdigest()


def test_ban_check_catches_examples(monkeypatch):
    # Synthetic names stand in for the real ones, which are stored only as hashes.
    monkeypatch.setattr(sys.modules[__name__], "BANNED_NAME_HASHES", {_h("zorblax"), _h("quux bot")})
    monkeypatch.setattr(sys.modules[__name__], "BANNED_PREFIX_HASHES", {(6, _h("frobni"))})
    assert find_banned("by Quux Bot") and find_banned("ask Zorblax.")
    assert not find_banned("zorblaxes and quux")                             # whole-word match only
    assert find_banned("the Frobnis") and find_banned("frobnicate")          # prefix match (plurals)
    assert not find_banned("frob")
    assert find_banned("a curated list") and find_banned("TODO: x")
    assert find_banned("Morpheus MoE") and not find_banned("Moen")


def test_absolute_path_check():
    for t in ("see /srv/data/x", "cd /opt/app", "path=/tmp/a", "`/usr/lib`"):
        assert find_banned(t), t
    for t in ("https://api.example.com/v1/chat", "/v1/models", "POST /chat/completions", "and/or", "a / b"):
        assert not find_banned(t), t


def test_validator_requires_changelog_entry_for_version(tmp_path):
    import shutil
    dst = tmp_path / "repo"
    shutil.copytree(ROOT, dst, ignore=shutil.ignore_patterns(".git", ".venv", "__pycache__", "*.egg-info"))
    cl = dst / "CHANGELOG.md"
    text = cl.read_text()
    version = re.search(r'"version":\s*"([^"]+)"', (dst / ".cursor-plugin/plugin.json").read_text()).group(1)
    cl.write_text(re.sub(rf"^## {re.escape(version)}\b", "## 9.9.9", text, flags=re.M))
    p = subprocess.run([sys.executable, str(dst / "scripts/validate_plugin.py")], capture_output=True, text=True)
    assert p.returncode != 0 and f"no entry for {version}" in p.stdout + p.stderr
