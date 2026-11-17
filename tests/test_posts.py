from unwatched.posts import add_source, load_posts, save_posts

SRC_A = {"kind": "saved", "name": "saved", "via": "export", "ts": "2025-10-31T08:40:00Z"}
SRC_B = {"kind": "dm", "name": "kungfookah", "via": "live", "ts": "2025-10-30T11:40:00Z"}


def test_add_source_creates_then_merges_and_keeps_earliest_first_seen():
    posts = {}
    assert add_source(posts, "AAAAAAAAAAA", SRC_A) is True
    assert add_source(posts, "AAAAAAAAAAA", SRC_B) is False
    assert add_source(posts, "AAAAAAAAAAA", SRC_B) is False
    rec = posts["AAAAAAAAAAA"]
    assert rec["url"] == "https://www.instagram.com/p/AAAAAAAAAAA/"
    assert rec["sources"] == [SRC_A, SRC_B]
    assert rec["first_seen"] == "2025-10-30T11:40:00Z"
    assert rec["local_media"] is None


def test_roundtrip_and_missing_file(tmp_path):
    assert load_posts(tmp_path) == {}
    posts = {}
    add_source(posts, "BBBBBBBBBBB", SRC_A)
    save_posts(tmp_path, posts)
    assert load_posts(tmp_path) == posts
    assert (tmp_path / "posts.jsonl").read_text(encoding="utf-8").count("\n") == 1
