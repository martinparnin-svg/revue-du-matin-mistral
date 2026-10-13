"""Écrit docs/feed.xml (flux podcast RSS lisible par AntennaPod) à partir des épisodes fabriqués."""
import glob
import json
import os
import subprocess
from datetime import datetime, timezone
from email.utils import format_datetime
from xml.sax.saxutils import escape


def duration_s(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                         capture_output=True, text=True).stdout.strip()
    return int(float(out or 0))


def write_feed(cfg, root):
    show = cfg["show"]
    base = show["base_url"].rstrip("/")
    audio_dir = os.path.join(root, "docs", "audio")
    mp3s = sorted(glob.glob(os.path.join(audio_dir, "*.mp3")), reverse=True)

    # on ne garde que les N derniers épisodes
    for old in mp3s[show.get("keep_episodes", 60):]:
        os.remove(old)
    mp3s = mp3s[: show.get("keep_episodes", 60)]

    items = []
    for mp3 in mp3s:
        date = os.path.basename(mp3)[:-4]
        meta_path = os.path.join(root, "episodes", f"{date}.json")
        ep = json.load(open(meta_path, encoding="utf-8")) if os.path.exists(meta_path) else {}
        title = ep.get("title", f"{show['title']} · {date}")
        desc = ep.get("summary", "")
        links = ep.get("links", {})
        if links.get("note"):
            desc += f"\n\nNote de veille et sources : {links['note']}"
        pub = datetime.strptime(date, "%Y-%m-%d").replace(hour=5, minute=30, tzinfo=timezone.utc)
        secs = duration_s(mp3)
        items.append(f"""    <item>
      <title>{escape(title)}</title>
      <description>{escape(desc)}</description>
      <enclosure url="{base}/audio/{date}.mp3" length="{os.path.getsize(mp3)}" type="audio/mpeg"/>
      <guid isPermaLink="false">revue-du-matin-{date}</guid>
      <pubDate>{format_datetime(pub)}</pubDate>
      <itunes:duration>{secs // 60}:{secs % 60:02d}</itunes:duration>
    </item>""")

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
  <channel>
    <title>{escape(show['title'])}</title>
    <link>{base}/</link>
    <description>{escape(show['description'])}</description>
    <language>{show['language']}</language>
    <itunes:author>{escape(show['author'])}</itunes:author>
    <itunes:image href="{base}/cover.png"/>
    <itunes:explicit>false</itunes:explicit>
    <itunes:block>Yes</itunes:block>
{chr(10).join(items)}
  </channel>
</rss>
"""
    with open(os.path.join(root, "docs", "feed.xml"), "w", encoding="utf-8") as f:
        f.write(xml)
    print(f"Flux mis à jour : {len(items)} épisode(s)")
