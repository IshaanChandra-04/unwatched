import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_plugin_manifest_and_skill_frontmatter():
    manifest = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert manifest["name"] == "unwatched" and manifest["version"] == "0.1.0"
    skill = (ROOT / "skills" / "unwatched" / "SKILL.md").read_text(encoding="utf-8")
    assert skill.startswith("---\nname: unwatched\n")
    assert "UNWATCHED_DIGEST_DONE kept=<n> total=<m>" in skill
    for profile in ("tech", "design", "cooking", "fashion"):
        text = (ROOT / "profiles" / f"{profile}.md").read_text(encoding="utf-8")
        assert all(k in text for k in ("Keep:", "Skip:", "Extract per post:", "Output:"))
