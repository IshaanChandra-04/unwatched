import json
import re
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


def test_ci_actions_are_pinned_to_commits():
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    uses = re.findall(r"uses: (\S+)", ci)
    assert uses and all(re.fullmatch(r"[\w.-]+/[\w.-]+@[0-9a-f]{40}", u) for u in uses)
