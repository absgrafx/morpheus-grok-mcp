import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_manifest_validates():
    p = subprocess.run([sys.executable, str(ROOT / "scripts/validate_plugin.py")],
                       capture_output=True, text=True)
    assert p.returncode == 0, p.stdout + p.stderr


def test_no_jargon_or_host_only_framing():
    banned = ["MoE", "Grok Bot", "NomadicRogue", "curated", "this PR"]
    files = [ROOT / "README.md", ROOT / ".cursor-plugin/plugin.json", ROOT / "pyproject.toml",
             ROOT / "src/morpheus_mcp/server.py", *ROOT.glob("skills/*/SKILL.md"),
             *ROOT.glob("docs/listing/*")]
    for f in files:
        text = f.read_text()
        for word in banned:
            assert word not in text, f"{word!r} found in {f.relative_to(ROOT)}"
