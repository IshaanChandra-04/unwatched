"""Regenerate the browser fixtures.

``dm_thread.html``: a column-reverse list of 60 reel cards, newest first in DOM order, each with a
thumbnail whose ``ig_cache_key`` is the URL-encoded base64 media id plus Instagram's CDN suffix.
``dm_thread_delayed.html``: the same cards inserted 1.5 seconds after load, the way Instagram
fills the list after the page's load event. ``saved_grid.html``: a tall page of 45 saved tiles,
newest first, each a link to its post.

Run: uv run python tests/fixtures/make_dm_fixture.py
"""

import base64
import json
from pathlib import Path
from urllib.parse import quote

DM_BASE = 3700000000000000000
GRID_BASE = 3800000000000000000
ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"


def shortcode(media_id: int) -> str:
    out = ""
    while media_id:
        media_id, rem = divmod(media_id, 64)
        out = ALPHABET[rem] + out
    return out or "A"


srcs = []
for i in range(59, -1, -1):
    key = quote(base64.b64encode(f"{DM_BASE + i}".encode()).decode()) + ".3-ccb7-5"
    srcs.append(f"https://cdn.example/x.jpg?stp=1&ig_cache_key={key}&_nc=1")

cards = "\n".join(
    f'  <div class="card"><img src="{s.replace("&", "&amp;")}" alt="reel {i}"></div>'
    for i, s in zip(range(59, -1, -1), srcs, strict=True)
)
profile = '  <div class="profile">alt_account · View profile</div>'

HEAD = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>alt_account • Instagram</title>
<style>
  #list { height: 600px; overflow-y: auto; display: flex; flex-direction: column-reverse; }
  .card { height: 120px; flex: none; }
  .profile { height: 200px; flex: none; }
</style>
</head>
<body>
"""
# Like the real page: the inbox sidebar has its own headings, and the conversation column is a
# plain section whose header names the other participant.
MAIN = (
    "<aside>\n<h1>my_own_handle</h1>\n<h2>Messages</h2>\n</aside>\n"
    "<section>\n<h2>alt_account</h2>\n"
)
immediate = (
    f'{HEAD}{MAIN}<div id="list">\n{cards}\n{profile}\n</div>\n</section>\n</body>\n</html>\n'
)
delayed = (
    f'{HEAD}{MAIN}<div id="list"></div>\n</section>\n<script>\n'
    f"const srcs = {json.dumps(srcs)};\n"
    "setTimeout(() => {\n"
    "  const list = document.getElementById('list');\n"
    "  for (const s of srcs) {\n"
    "    const d = document.createElement('div'); d.className = 'card';\n"
    "    const img = document.createElement('img'); img.src = s; d.appendChild(img);\n"
    "    list.appendChild(d);\n"
    "  }\n"
    "  const p = document.createElement('div'); p.className = 'profile';\n"
    "  p.textContent = 'alt_account · View profile'; list.appendChild(p);\n"
    "}, 1500);\n"
    "</script>\n</body>\n</html>\n"
)

tiles = "\n".join(
    f'  <a class="tile" href="https://www.instagram.com/p/{shortcode(GRID_BASE + i)}/">tile {i}</a>'
    for i in range(44, -1, -1)
)
grid = (
    '<!doctype html>\n<html>\n<head>\n<meta charset="utf-8">\n<title>Saved • Instagram</title>\n'
    "<style>\n  .tile { display: block; height: 300px; }\n</style>\n</head>\n<body>\n"
    f"<main>\n{tiles}\n</main>\n</body>\n</html>\n"
)

# Like Instagram's real grid: 12 tiles at a time, the next batch appended when the viewer nears
# the bottom, earlier tiles kept in the DOM.
lazy_hrefs = [f"https://www.instagram.com/p/{shortcode(GRID_BASE + i)}/" for i in range(59, -1, -1)]
lazy = (
    '<!doctype html>\n<html>\n<head>\n<meta charset="utf-8">\n<title>Saved • Instagram</title>\n'
    "<style>\n  .tile { display: block; height: 300px; }\n</style>\n</head>\n<body>\n"
    '<main id="grid"></main>\n<script>\n'
    f"const hrefs = {json.dumps(lazy_hrefs)};\nlet next = 0;\n"
    "function more() {\n"
    "  const grid = document.getElementById('grid');\n"
    "  for (let i = 0; i < 12 && next < hrefs.length; i++, next++) {\n"
    "    const a = document.createElement('a'); a.className = 'tile'; a.href = hrefs[next];\n"
    "    a.textContent = 'tile ' + next; grid.appendChild(a);\n"
    "  }\n"
    "}\n"
    "more();\n"
    "window.addEventListener('scroll', () => {\n"
    "  if (window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 600) {\n"
    "    setTimeout(more, 20);\n"
    "  }\n"
    "});\n"
    "</script>\n</body>\n</html>\n"
)

here = Path(__file__).parent
(here / "dm_thread.html").write_text(immediate, encoding="utf-8")
(here / "dm_thread_delayed.html").write_text(delayed, encoding="utf-8")
(here / "saved_grid.html").write_text(grid, encoding="utf-8")
(here / "saved_grid_lazy.html").write_text(lazy, encoding="utf-8")
print("wrote dm_thread.html, dm_thread_delayed.html, saved_grid.html, saved_grid_lazy.html")
