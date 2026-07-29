# -*- coding: utf-8 -*-
"""按游戏名抓新闻 RSS，刷新 news.json。

- 主源 Bing News RSS（apiclick 链接的 url= 参数解码为直链）
- Bing 无结果时回退 Google News RSS（链接为 Google 跳转页，浏览器可正常打开）
- 只刷新「近期/即将发售」（-60d ~ +365d）或已有新闻记录的游戏，控制请求量
- 每游戏保留最新 3 条，新旧合并按标题去重
"""
import re
import sys
import time
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DATA, OUT_DIR, load_json, save_json, http_get, clean  # noqa: E402

BING_RSS = "https://www.bing.com/news/search?q={q}&format=rss&setlang=en&cc=us"
GOOGLE_RSS = "https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
KEEP = 3
SLEEP = 0.8
WINDOW_PAST_DAYS = 60
WINDOW_FUTURE_DAYS = 365

_SOURCE_ALIAS = {
    "forbes.com": "Forbes", "automaton-media.com": "Automaton",
    "pcgamesn.com": "PCGamesN", "rockpapershotgun.com": "RockPaperShotgun",
    "eurogamer.net": "Eurogamer", "ign.com": "IGN", "gamespot.com": "GameSpot",
    "gematsu.com": "Gematsu", "msn.com": "MSN", "videogameschronicle.com": "VGC",
    "gamesradar.com": "GamesRadar+", "polygon.com": "Polygon",
    "thegamer.com": "TheGamer", "gamedeveloper.com": "GameDeveloper",
    "4gamer.net": "4Gamer", "famitsu.com": "Famitsu", "ign.jp": "IGN Japan",
}


def strip_html(s):
    s = re.sub(r"<[^>]+>", " ", s or "")
    s = re.sub(r"&nbsp;?", " ", s)
    s = re.sub(r"&amp;", "&", s)
    s = re.sub(r"&#39;|&apos;", "'", s)
    s = re.sub(r"&quot;", '"', s)
    s = re.sub(r"&lt;", "<", s)
    s = re.sub(r"&gt;", ">", s)
    return clean(s)[:220]


def domain_source(url):
    d = re.sub(r"^www\.", "", urllib.parse.urlparse(url).netloc.lower())
    if d in _SOURCE_ALIAS:
        return _SOURCE_ALIAS[d]
    return d.split(".")[0].capitalize() if d else ""


def parse_pubdate(s):
    try:
        return parsedate_to_datetime(s).strftime("%Y-%m-%d")
    except Exception:  # noqa: BLE001
        return ""


def fetch_bing(name):
    q = urllib.parse.quote(f'"{name}"')
    body = http_get(BING_RSS.format(q=q), timeout=15, retries=1)
    items = []
    for it in ET.fromstring(body).iter("item"):
        link = clean(it.findtext("link"))
        m = re.search(r"[?&]url=([^&]+)", link)
        if m:
            link = urllib.parse.unquote(m.group(1))
        items.append({"title": clean(it.findtext("title")), "url": link,
                      "source": domain_source(link),
                      "date": parse_pubdate(it.findtext("pubDate") or ""),
                      "snippet": strip_html(it.findtext("description"))})
    return items


def fetch_google(name):
    q = urllib.parse.quote(f'"{name}"')
    body = http_get(GOOGLE_RSS.format(q=q), timeout=15, retries=1)
    items = []
    for it in ET.fromstring(body).iter("item"):
        src = it.find("source")
        items.append({"title": clean(it.findtext("title")),
                      "url": clean(it.findtext("link")),
                      "source": clean(src.text) if src is not None else "",
                      "date": parse_pubdate(it.findtext("pubDate") or ""),
                      "snippet": strip_html(it.findtext("description"))})
    return items


def norm_title(t):
    return re.sub(r"\W+", "", (t or "").lower())


def game_date(g):
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", g.get("date") or "")
    if m:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return None


def run(max_games=None):
    games = load_json(DATA / "games.json")
    news = load_json(DATA / "news.json")
    today = datetime.now()
    lo = today - timedelta(days=WINDOW_PAST_DAYS)
    hi = today + timedelta(days=WINDOW_FUTURE_DAYS)

    targets = {}
    for track in ("a", "l", "m"):
        for g in games.get(track, []):
            cn = g.get("cn", "")
            dt = game_date(g)
            in_window = dt is not None and lo <= dt <= hi
            if in_window or cn in news:
                targets[cn] = clean(g.get("en")) or cn

    report = {"time": datetime.now().isoformat(timespec="seconds"),
              "fetched": 0, "google_fallback": [], "new_items": 0, "errors": []}
    count = 0
    for cn, name in targets.items():
        if max_games and count >= max_games:
            break
        count += 1
        try:
            items = fetch_bing(name)
            if not items:
                items = fetch_google(name)
                if items:
                    report["google_fallback"].append(cn)
            report["fetched"] += 1
        except Exception as e:  # noqa: BLE001
            report["errors"].append({"cn": cn, "error": str(e)})
            time.sleep(SLEEP)
            continue
        time.sleep(SLEEP)
        old = news.get(cn, [])
        old_keys = {norm_title(x.get("title")) for x in old}
        items.sort(key=lambda x: x.get("date") or "", reverse=True)
        fresh = []
        for it in items:
            if len(fresh) >= KEEP:
                break
            if norm_title(it["title"]) not in old_keys:
                fresh.append(it)
        report["new_items"] += len(fresh)
        merged = fresh + old
        merged.sort(key=lambda x: x.get("date") or "", reverse=True)
        if merged:
            news[cn] = merged[:KEEP]

    save_json(DATA / "news.json", news, pretty=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    save_json(OUT_DIR / f"news_report_{ts}.json", report, pretty=True)
    save_json(OUT_DIR / "news_report_latest.json", report, pretty=True)
    print(f"[news] targets={len(targets)} fetched={report['fetched']} "
          f"new_items={report['new_items']} google_fallback={len(report['google_fallback'])} "
          f"errors={len(report['errors'])}")
    for e in report["errors"][:10]:
        print(f"  ! {e['cn']}: {e['error']}")
    return report


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-games", type=int, default=None)
    args = ap.parse_args()
    run(max_games=args.max_games)
