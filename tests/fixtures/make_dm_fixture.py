"""Regenerate dm_thread.html: a column-reverse list of 60 reel cards, newest first in DOM order.

Run: uv run python tests/fixtures/make_dm_fixture.py
"""

import base64
from pathlib import Path

BASE_ID = 3700000000000000000
COUNT = 60

cards = []
for i in range(COUNT - 1, -1, -1):
    key = base64.b64encode(f"{BASE_ID + i}_1".encode()).decode()
    cards.append(
        f'  <div class="card"><img src="https://cdn.example/x.jpg?stp=1&amp;ig_cache_key={key}'
        f'&amp;_nc=1" alt="reel {i}"></div>'
    )

html = f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>kungfookah • Instagram</title>
<style>
  #list {{ height: 600px; overflow-y: auto; display: flex; flex-direction: column-reverse; }}
  .card {{ height: 120px; flex: none; }}
  .profile {{ height: 200px; flex: none; }}
</style>
</head>
<body>
<div id="list">
{chr(10).join(cards)}
  <div class="profile">kungfookah · View profile</div>
</div>
</body>
</html>
"""
Path(__file__).with_name("dm_thread.html").write_text(html, encoding="utf-8")
print(f"wrote dm_thread.html with {COUNT} cards")
