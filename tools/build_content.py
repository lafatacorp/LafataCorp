#!/usr/bin/env python3
"""
build_content.py -- render the hand-kept lists into the static pages.

Two lists live in data/ and are the only thing to edit:

  data/clips.json   Media page clips. Each entry:
                      {"title": "...", "outlet": "96.7/1310 The Ticket",
                       "date": "2026-11-20", "url": "https://...",
                       "kind": "audio" | "video"}
                    Newest first on the page whatever the order here. An
                    audio URL ending in .mp3/.m4a/.wav/.ogg gets an inline
                    player; anything else renders as a Listen/Watch link.

  data/quotes.json  About page, "In their words". Each entry:
                      {"group": "on_air" | "written",
                       "quote": "...", "name": "...", "title": "...",
                       "photo": "/quotes/name.jpg" or "",
                       "source": "show name or publication",
                       "date": "2026-11-20" or "",
                       "audio": "https://..." or "",
                       "published": false}
                    Only entries with "published": true render. Photos must
                    be files added under /quotes/ by hand, never pulled from
                    the web; a photo path that does not exist is dropped.

What it writes, all between <!-- TAG --> markers so nothing else moves:

  media/index.html   <!-- CLIPS -->       empty when there are no clips
  about/index.html   <!-- QUOTES -->      empty when nothing is published
  every page's nav   <!-- NAVMEDIA -->    the Media link, only once a clip
                                          exists; /media/ stays live either way

Polaris is not touched: its pages are published by their own pipeline.

Usage:
    python3 tools/build_content.py           # write the pages
    python3 tools/build_content.py --check   # report, write nothing
"""

import argparse
import html
import json
import os
import re
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLIPS = os.path.join(ROOT, "data", "clips.json")
QUOTES = os.path.join(ROOT, "data", "quotes.json")
MEDIA_PAGE = os.path.join(ROOT, "media", "index.html")
ABOUT_PAGE = os.path.join(ROOT, "about", "index.html")
NAV_PAGES = ["index.html", "nhl/index.html", "nhl/weeks/index.html",
             "fantasy/index.html", "kalshi/index.html", "media/index.html",
             "about/index.html"]
AUDIO_FILE = re.compile(r"\.(mp3|m4a|wav|ogg)(\?.*)?$", re.I)


def load(path):
    if not os.path.exists(path):
        return []
    with open(path) as f:
        data = json.load(f)
    if not isinstance(data, list):
        sys.exit(f"{path}: expected a JSON list")
    return data


def inject(text, tag, value, where):
    pattern = rf"<!-- {tag} -->.*?<!-- /{tag} -->"
    if not re.search(pattern, text, flags=re.S):
        sys.exit(f"{where}: no <!-- {tag} --> marker")
    return re.sub(pattern, lambda m: f"<!-- {tag} -->{value}<!-- /{tag} -->",
                  text, flags=re.S)


def guard(text, where):
    """The site's two standing rules, checked on what this script wrote."""
    if "—" in text or "&mdash;" in text:
        sys.exit(f"{where}: em dash in rendered copy")
    if re.search(r"\$\s?-?\d", text):
        sys.exit(f"{where}: currency figure in rendered copy")


def nice_date(iso):
    try:
        return datetime.strptime(iso, "%Y-%m-%d").strftime("%b %-d, %Y")
    except (TypeError, ValueError):
        return iso or ""


def e(s):
    return html.escape(str(s or ""), quote=True)


def render_clips(clips):
    if not clips:
        return ""
    rows = []
    for c in sorted(clips, key=lambda c: c.get("date") or "", reverse=True):
        url, kind = c.get("url") or "", (c.get("kind") or "audio").lower()
        if kind == "audio" and AUDIO_FILE.search(url):
            play = f'<audio controls preload="none" src="{e(url)}"></audio>'
        elif url:
            verb = "Watch" if kind == "video" else "Listen"
            play = (f'<a class="clip-go" href="{e(url)}" target="_blank" '
                    f'rel="noopener">{verb}<span class="visually-hidden">: '
                    f'{e(c.get("title"))}</span></a>')
        else:
            play = ""
        rows.append(
            '<li class="clip">'
            f'<time datetime="{e(c.get("date"))}">{e(nice_date(c.get("date")))}</time>'
            f'<div><h3>{e(c.get("title"))}</h3><p>{e(c.get("outlet"))}</p></div>'
            f'<span class="clip-kind">{"Video" if kind == "video" else "Audio"}</span>'
            f'<div class="clip-play">{play}</div></li>')
    return ('<section class="clips" aria-labelledby="clips-h">'
            '<h2 id="clips-h">Clips</h2>'
            f'<ol class="clip-list">{"".join(rows)}</ol></section>')


def render_quotes(quotes):
    live = [q for q in quotes if q.get("published") is True and q.get("quote")]
    if not live:
        return ""

    def photo(q):
        p = q.get("photo") or ""
        # Only files that were added to the site by hand.
        if p.startswith("/") and os.path.exists(os.path.join(ROOT, p.lstrip("/"))):
            return f'<img src="{e(p)}" alt="" width="56" height="56" loading="lazy">'
        return ""

    def who(q):
        bits = [f'<b>{e(q.get("name"))}</b>']
        if q.get("title"):
            bits.append(f'<span>{e(q["title"])}</span>')
        return f'<figcaption>{photo(q)}<span class="q-who">{"".join(bits)}</span></figcaption>'

    on_air = [q for q in live if q.get("group") == "on_air"]
    written = [q for q in live if q.get("group") != "on_air"]
    parts = []
    if on_air:
        items = []
        for q in on_air:
            src = " &middot; ".join(e(x) for x in (q.get("source"), nice_date(q.get("date"))) if x)
            audio = (f'<audio controls preload="none" src="{e(q["audio"])}"></audio>'
                     if q.get("audio") else "")
            items.append(f'<li><figure class="q-air"><blockquote><p>{e(q["quote"])}</p>'
                         f'</blockquote>{who(q)}<p class="q-src">{src}</p>{audio}</figure></li>')
        parts.append('<div class="q-group"><h3>On air</h3>'
                     f'<ul class="q-air-list">{"".join(items)}</ul></div>')
    if written:
        items = []
        for q in written:
            src = f'<p class="q-src">{e(q.get("source"))}</p>' if q.get("source") else ""
            items.append(f'<li><figure class="q-written"><blockquote><p>{e(q["quote"])}</p>'
                         f'</blockquote>{who(q)}{src}</figure></li>')
        parts.append('<div class="q-group"><h3>In writing</h3>'
                     f'<ul class="q-written-list">{"".join(items)}</ul></div>')
    return ('<section class="quotes" aria-labelledby="quotes-h">'
            '<h2 id="quotes-h">In their words</h2>' + "".join(parts) + '</section>')


def nav_link(page_rel, show):
    if not show:
        return ""
    current = ' aria-current="page"' if page_rel == "media/index.html" else ""
    return f'<a href="/media/"{current}>Media</a>'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    clips, quotes = load(CLIPS), load(QUOTES)
    show_media = bool(clips)
    writes = {}

    media = open(MEDIA_PAGE).read()
    media = inject(media, "CLIPS", render_clips(clips), MEDIA_PAGE)
    writes[MEDIA_PAGE] = media

    about = open(ABOUT_PAGE).read()
    about = inject(about, "QUOTES", render_quotes(quotes), ABOUT_PAGE)
    writes[ABOUT_PAGE] = about

    for rel in NAV_PAGES:
        path = os.path.join(ROOT, rel)
        text = writes.get(path) or open(path).read()
        writes[path] = inject(text, "NAVMEDIA", nav_link(rel, show_media), path)

    for path, text in writes.items():
        guard(text, path)

    published = sum(1 for q in quotes if q.get("published") is True)
    print(f"clips: {len(clips)} | quotes: {published} of {len(quotes)} published | "
          f"Media in nav: {'yes' if show_media else 'no'}")
    if args.check:
        return
    for path, text in writes.items():
        with open(path) as f:
            if f.read() == text:
                continue
        with open(path, "w") as f:
            f.write(text)
        print(f"wrote {os.path.relpath(path, ROOT)}")


if __name__ == "__main__":
    main()
