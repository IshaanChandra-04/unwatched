import json
import zipfile
from pathlib import Path

from unwatched.build import due
from unwatched.ingest import apply, fix_text, ingest_export, ingest_links, iso_from_epoch
from unwatched.posts import load_posts
from unwatched.state import load_state

FIX = Path(__file__).parent / "fixtures" / "export"
LINKS = Path(__file__).parent / "fixtures" / "links.md"


def test_fix_text_repairs_mojibake_and_leaves_plain_text():
    assert fix_text("cafÃ© tips") == "café tips"
    assert fix_text("plain") == "plain"


def test_iso_from_epoch_units():
    assert iso_from_epoch(1761900000, "s") == "2025-10-31T08:40:00Z"
    assert iso_from_epoch(1761910800000, "ms") == "2025-10-31T11:40:00Z"


def test_ingest_export_folder_finds_every_source():
    found = ingest_export(FIX)
    by_code = {}
    for code, src, _ in found:
        by_code.setdefault(code, []).append(src["kind"])
    assert by_code["AAAAAAAAAAA"] == ["saved", "dm"]
    assert by_code["BBBBBBBBBBB"] == ["saved"]
    assert by_code["CCCCCCCCCCC"] == ["liked"]
    assert by_code["DDDDDDDDDDD"] == ["dm"]
    assert by_code["archived-1761921600"] == ["archived"]
    dm = [s for c, s, _ in found if c == "AAAAAAAAAAA" and s["kind"] == "dm"][0]
    assert dm["name"] == "alt_account"
    assert dm["text"] == "café tips"
    assert dm["ts"] == "2025-10-31T11:40:00Z"


def test_ingest_export_zip_with_nested_top_folder(tmp_path):
    zpath = tmp_path / "export.zip"
    with zipfile.ZipFile(zpath, "w") as z:
        for p in FIX.rglob("*"):
            if p.is_file():
                z.write(p, "instagram-me-2026/" + p.relative_to(FIX).as_posix())
    found = ingest_export(zpath)
    assert {c for c, _, _ in found} == {
        "AAAAAAAAAAA",
        "BBBBBBBBBBB",
        "CCCCCCCCCCC",
        "DDDDDDDDDDD",
        "archived-1761921600",
    }
    apply(tmp_path / "w", found)
    media = load_posts(tmp_path / "w")["archived-1761921600"]["local_media"]
    assert media and Path(media).exists() and Path(media).name == "archived-1761921600.mp4"


def test_apply_survives_archived_media_missing_from_the_zip(tmp_path):
    zpath = tmp_path / "part2.zip"
    with zipfile.ZipFile(zpath, "w") as z:
        z.write(
            FIX / "your_instagram_activity" / "content" / "archived_posts.json",
            "x/your_instagram_activity/content/archived_posts.json",
        )
    apply(tmp_path / "w", ingest_export(zpath))
    assert load_posts(tmp_path / "w")["archived-1761921600"]["local_media"] is None


def test_ingest_links_file():
    found = ingest_links(LINKS)
    assert [c for c, _, _ in found] == ["EEEEEEEEEEE", "AAAAAAAAAAA"]
    assert found[0][1] == {"kind": "links", "name": "links.md", "via": "file", "ts": None}


def test_apply_merges_counts_and_archived_media(tmp_path):
    counts = apply(tmp_path, ingest_export(FIX))
    posts = load_posts(tmp_path)
    assert len(posts) == 5
    assert counts["dm:alt_account"] == 2 and counts["saved:saved"] == 2
    assert posts["archived-1761921600"]["url"] is None
    assert Path(posts["archived-1761921600"]["local_media"]).name == "vid.mp4"


def test_apply_seen_records_seeded_posts_as_digested(tmp_path):
    apply(tmp_path, ingest_links(LINKS), seen=True)
    meta = json.loads((tmp_path / "meta" / "EEEEEEEEEEE.json").read_text(encoding="utf-8"))
    assert meta["skipped"] == "seeded"
    state = load_state(tmp_path)
    assert "EEEEEEEEEEE" in state["digested"] and state["last_digest"] is not None
    assert due(tmp_path, load_posts(tmp_path), state) == []


def test_ingest_export_skips_a_file_it_cannot_parse(tmp_path, caplog):
    import shutil

    export = tmp_path / "export"
    shutil.copytree(FIX, export)
    bad = export / "your_instagram_activity" / "content" / "archived_posts.json"
    bad.write_text(
        '{"ig_archived_post_media": [{"media": [{"no": "timestamp"}]}]}', encoding="utf-8"
    )
    found = ingest_export(export)
    assert len(found) == 5  # saved 2, dm 2, liked 1; only the archived post is gone
    assert "archived_posts.json" in caplog.text and "skipped" in caplog.text
