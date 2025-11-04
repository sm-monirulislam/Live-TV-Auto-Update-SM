from dataclasses import dataclass
from collections import defaultdict
from datetime import datetime, timezone, timedelta
import json, re, functools, time, os

# ---------- simple console helpers (no colors)

def banner(title: str):
    bar = "-" * len(title)
    print(bar)
    print(title)
    print(bar)

def kv(label: str, value: str, icon: str = "•"):
    print(f"{icon} {label}: {value}")

print = functools.partial(print, flush=True)

# ---------- config

YT_FILE = "YT_playlist.m3u"
JSON_FILE = "static_channels.json"
OUTPUT_FILE = "combined.m3u"

GROUP_ORDER = [
    "Bangla",
    "Bangla News",
    "International News",
    "India","Pakistan",
    "Educational",
    "Music",
    "International",
    "Travel",
    "Sports",
    "Religious",
    "Kids",
]

# ---------- helpers

@dataclass
class Item:
    header: str
    link: str
    group: str
    tvg_id: str | None
    tvg_logo: str | None
    name: str = ""
    source_rank: int = 99

def channel_display_name(header: str) -> str:
    return header.split(",", 1)[-1].strip()

def generate_tvg_id(name): 
    return re.sub(r'[^A-Za-z0-9_]', '_', name.strip())

# ---------- parsers

def parse_m3u(path: str) -> list[Item]:
    out = []
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            lines = [ln.strip() for ln in f]
    except FileNotFoundError:
        print(f"⚠️  {path} not found. Skipping.")
        return out

    header = link = group = tvg_id = tvg_logo = None
    for ln in lines:
        if ln.startswith("#EXTINF"):
            header = ln
            group = (re.search(r'group-title="([^"]+)"', ln) or [None,"Other"])[1]
            tvg_id = (re.search(r'tvg-id="([^"]*)"', ln) or [None,None])[1]
            tvg_logo = (re.search(r'tvg-logo="([^"]*)"', ln) or [None,None])[1]
        elif ln and not ln.startswith("#"):
            link = ln
            if header and link:
                name = channel_display_name(header)
                out.append(Item(header, link, group, tvg_id, tvg_logo, name=name, source_rank=3))
            header = link = None
    return out

def parse_json_channels(path: str) -> list[Item]:
    out = []
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"⚠️  {path} not found. Skipping.")
        return out
    for name, info in data.items():
        group = info.get("group", "Other")
        tvg_id = info.get("tvg_id") or generate_tvg_id(name)
        tvg_logo = info.get("tvg_logo")
        links = info.get("links", [])
        online = next((l["url"] for l in links if l.get("status") == "online"), None)
        if online:
            header = f'#EXTINF:-1 group-title="{group}",{name}'
            out.append(Item(header, online, group, tvg_id, tvg_logo, name=name, source_rank=2))
    return out

# ---------- output

def save_m3u(items: list[Item], output_file: str):
    _EPG_URL = "https://raw.githubusercontent.com/time2shine/IPTV/refs/heads/master/epg.xml"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(f"#EXTM3U url-tvg=\"{_EPG_URL}\" x-tvg-url=\"{_EPG_URL}\"\n")
        for it in items:
            base, name = it.header.split(",", 1)[0], it.name
            if it.tvg_id:
                base = re.sub(r'tvg-id="[^"]*"', f'tvg-id="{it.tvg_id}"', base) if 'tvg-id="' in base else f'{base} tvg-id="{it.tvg_id}"'
            if it.tvg_logo:
                base = re.sub(r'tvg-logo="[^"]*"', f'tvg-logo="{it.tvg_logo}"', base) if 'tvg-logo="' in base else f'{base} tvg-logo="{it.tvg_logo}"'
            f.write(f"{base},{name}\n{it.link}\n")

# ---------- main

def main():
    start = time.time()
    banner("🎛️ IPTV Playlist Builder")

    print("📂 Reading sources…")
    yt = parse_m3u(YT_FILE)
    kv("M3U channels", str(len(yt)), "📼")

    chans = parse_json_channels(JSON_FILE)
    kv("Static channels (online)", str(len(chans)), "📡")

    # Combine & dedupe
    combined = chans + yt

    by_name = {}
    duplicates_removed = 0
    for it in combined:
        key = it.name
        if key not in by_name:
            by_name[key] = it
        else:
            duplicates_removed += 1

    kv("Duplicates removed", str(duplicates_removed), "🔁")

    # Grouping & sorting
    groups = defaultdict(list)
    for it in by_name.values():
        groups[it.group].append(it)

    for g in groups:
        groups[g].sort(key=lambda x: x.name.lower())

    out = []
    for g in GROUP_ORDER + sorted(k for k in groups.keys() if k not in GROUP_ORDER):
        out.extend(groups.get(g, []))

    save_m3u(out, OUTPUT_FILE)

    kv("Output items", str(len(out)), "✅")
    kv("Saved as", OUTPUT_FILE, "💾")

    elapsed = time.time() - start
    kv("Elapsed", f"{elapsed:.2f}s", "⏱")
    print("\n✨ Done! No Movies ✅")

if __name__ == "__main__":
    main()
