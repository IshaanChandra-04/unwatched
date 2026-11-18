from pathlib import Path

import av
from PIL import Image

from unwatched.frames import run_frames, sample

SIZE = (160, 288)


def colour(i: int) -> tuple[int, int, int]:
    return ((i * 37) % 256, (i * 91) % 256, (i * 151) % 256)


def make_video(path: Path, scenes: int, seconds_each: float, fps: int = 10) -> None:
    """A video of solid-colour scenes, one colour per scene, encoded with PyAV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with av.open(str(path), "w") as container:
        stream = container.add_stream("mpeg4", rate=fps)
        stream.width, stream.height = SIZE
        stream.pix_fmt = "yuv420p"
        for i in range(scenes):
            img = Image.new("RGB", SIZE, colour(i))
            for _ in range(int(seconds_each * fps)):
                for packet in stream.encode(av.VideoFrame.from_image(img)):
                    container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)


def _close(a: tuple[int, ...], b: tuple[int, ...]) -> bool:
    return all(abs(x - y) < 40 for x, y in zip(a, b, strict=True))


def test_sample_keeps_one_frame_per_scene(tmp_path):
    make_video(tmp_path / "v.mp4", scenes=3, seconds_each=2)
    out = sample(tmp_path / "v.mp4", tmp_path / "f")
    assert [p.name for p in out] == ["01.jpg", "02.jpg", "03.jpg"]
    assert Image.open(out[0]).size == SIZE  # small frames are left alone
    pixels = [Image.open(p).convert("RGB").getpixel((5, 5)) for p in out]
    assert all(_close(px, colour(i)) for i, px in enumerate(pixels))


def test_sample_caps_the_count_and_keeps_the_first_frame(tmp_path):
    make_video(tmp_path / "v.mp4", scenes=20, seconds_each=0.5)
    out = sample(tmp_path / "v.mp4", tmp_path / "f")
    assert len(out) == 12 and out[0].name == "01.jpg" and out[-1].name == "12.jpg"
    assert _close(Image.open(out[0]).convert("RGB").getpixel((5, 5)), colour(0))


def test_run_frames_samples_videos_without_frames_and_skips_the_rest(tmp_path):
    make_video(tmp_path / "video" / "AAAAAAAAAAA.mp4", scenes=2, seconds_each=1)
    make_video(tmp_path / "video" / "BBBBBBBBBBB.mp4", scenes=2, seconds_each=1)
    (tmp_path / "frames" / "BBBBBBBBBBB").mkdir(parents=True)
    posts = {"AAAAAAAAAAA": {}, "BBBBBBBBBBB": {}, "CCCCCCCCCCC": {}}
    assert run_frames(tmp_path, posts, None) == {"sampled": 1, "failed": 0}
    assert len(list((tmp_path / "frames" / "AAAAAAAAAAA").iterdir())) == 2
    assert run_frames(tmp_path, posts, None) == {"sampled": 0, "failed": 0}
    assert run_frames(tmp_path, posts, {"AAAAAAAAAAA"}) == {"sampled": 1, "failed": 0}


def test_run_frames_survives_a_broken_video(tmp_path):
    (tmp_path / "video").mkdir()
    (tmp_path / "video" / "AAAAAAAAAAA.mp4").write_bytes(b"nope")
    counts = run_frames(tmp_path, {"AAAAAAAAAAA": {}}, None)
    assert counts == {"sampled": 0, "failed": 1}
    assert (tmp_path / "frames" / "AAAAAAAAAAA").is_dir()  # so it is not retried daily
