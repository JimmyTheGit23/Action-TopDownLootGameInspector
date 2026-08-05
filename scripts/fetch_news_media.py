# -*- coding: utf-8 -*-
"""从 18 个媒体源 RSS + Steam News API 抓取游戏新闻，更新 news.json 与 index.html 内联。

设计：
- 每个媒体源 RSS 解析为 {title, url, source, date, snippet}
- 用游戏名（中文 cn + 英文 en，大小写不敏感）匹配文章标题
- Steam News API 补充有 appid 的游戏
- 与现有 news.json 合并，每游戏保留最新 10 条（按日期降序）
- 写回 news.json + index.html 内联 GAME_NEWS
- 不改动 fetch_news.py / fetch_steam_dates.py / 日期刷新脚本

用法：
  python fetch_news_media.py                 # 抓取 + 更新 + 输出报告
  python fetch_news_media.py --commit        # 额外 git commit
  python fetch_news_media.py --commit --push # 额外 commit + push
"""
import argparse
import json
import re
import sys
import time
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DATA, OUT_DIR, ROOT, INDEX, load_json, save_json, http_get, clean, js_spaced  # noqa: E402

NEWS_JSON = DATA / "news.json"
GAMES_JSON = DATA / "games.json"
STEAM_JSON = DATA / "steam_data.json"
MAX_PER_GAME = 10  # 每游戏保留最新条数
SLEEP = 0.5

# ============ 18 个媒体源 RSS ============
# lang: zh/en/ja —— 用于判断是否需要中文翻译标注
RSS_SOURCES = [
    # 中文源
    {"name": "GameLook", "url": "http://www.gamelook.com.cn/?feed=rss2", "lang": "zh"},
    {"name": "机核", "url": "https://www.gcores.com/rss", "lang": "zh"},
    # 17173 / 游民星空 暂无公开 RSS（404），如后续发现可补回
    # 英文源
    {"name": "GamesIndustry.biz", "url": "https://www.gamesindustry.biz/feed", "lang": "en"},
    # IGN 已停用 RSS（feeds.ign.com 501，/articles.rss 404），如后续恢复可补回
    {"name": "PC Gamer", "url": "https://www.pcgamer.com/rss/", "lang": "en"},
    {"name": "PCGamesN", "url": "https://www.pcgamesn.com/mainrss.xml", "lang": "en"},
    {"name": "Rock Paper Shotgun", "url": "https://www.rockpapershotgun.com/feed", "lang": "en"},
    {"name": "VG247", "url": "https://www.vg247.com/feed", "lang": "en"},
    {"name": "Eurogamer", "url": "https://www.eurogamer.net/feed", "lang": "en"},
    {"name": "GamesRadar+", "url": "https://www.gamesradar.com/rss/", "lang": "en"},
    # 日文源
    {"name": "Automaton", "url": "https://automaton-media.com/feed/", "lang": "ja"},
    {"name": "4Gamer", "url": "http://www.4gamer.net/rss/index.xml", "lang": "ja"},  # RSS 1.0 (RDF)
]

STEAM_NEWS_API = "https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid={appid}&count=5&maxlength=300&format=json"

# Bing News RSS —— 补充覆盖无 RSS 的中文媒体（3DM/游民/17173/游侠等）
BING_NEWS_RSS = "https://www.bing.com/news/search?q={q}&format=rss&setlang=en&cc=us"
# 仅对近期/即将发售的游戏搜 Bing（控制请求量）
BING_WINDOW_PAST_DAYS = 90
BING_WINDOW_FUTURE_DAYS = 365

# Google Translate 非官方接口（免费，无需 key）
GTRANSLATE_API = "https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=zh-CN&dt=t&q={q}"
TRANSLATE_SLEEP = 0.5


def translate_title(title):
    """调 Google Translate 非官方接口翻译标题，返回中文翻译或 None。"""
    if not title or not title.strip():
        return None
    try:
        url = GTRANSLATE_API.format(q=urllib.parse.quote(title))
        raw = http_get(url, timeout=10, retries=1)
        d = json.loads(raw)
        return "".join(s[0] for s in d[0] if s and s[0])
    except Exception as e:
        print(f"    [WARN] translate: {str(e)[:50]}")
        return None


def is_chinese(s):
    """判断字符串是否含中文字符。"""
    return bool(re.search(r"[\u4e00-\u9fa5]", s or ""))


# ============ RSS 解析 ============
def parse_date(s):
    """解析 RSS pubDate（RFC822）或 ISO 8601，返回 YYYY-MM-DD。"""
    if not s:
        return ""
    s = clean(s)
    # RFC822: "Wed, 02 Jul 2025 10:30:00 +0000"
    try:
        dt = parsedate_to_datetime(s)
        return dt.strftime("%Y-%m-%d")
    except Exception:
        pass
    # ISO 8601: "2025-07-02T10:30:00Z" / "2025-07-02T10:30:00+08:00"
    m = re.match(r"^(\d{4}-\d{2}-\d{2})", s)
    if m:
        return m.group(1)
    return ""


def parse_rss(xml_text, source_name, lang):
    """解析 RSS 2.0 / Atom / RSS 1.0 (RDF)，返回文章列表。"""
    articles = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        print(f"  [WARN] {source_name} XML 解析失败: {e}")
        return articles

    # RSS 2.0: <rss><channel><item>
    # Atom: <feed><entry>
    # RSS 1.0 (RDF): <rdf:RDF><item>
    ns = {"atom": "http://www.w3.org/2005/Atom",
          "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
          "rss10": "http://purl.org/rss/1.0/",
          "dc": "http://purl.org/dc/elements/1.1/"}

    items = root.findall(".//item")
    if not items:
        items = root.findall(".//atom:entry", ns)

    for it in items:
        title = ""
        link = ""
        pub = ""
        desc = ""

        # RSS 2.0 / RSS 1.0 (title/link/pubDate/description 无命名空间；RDF 用 dc:date)
        t = it.find("title")
        if t is not None and t.text:
            title = clean(t.text)
        l = it.find("link")
        if l is not None and l.text:
            link = clean(l.text)
        elif l is not None:
            link = l.get("href", "")  # Atom
        if not link:
            # RDF: link 作为元素，文本在 it
            l = it.find("{http://purl.org/rss/1.0/}link")
            if l is not None and l.text:
                link = clean(l.text)
        d = it.find("pubDate")
        if d is not None and d.text:
            pub = d.text
        else:
            d = it.find("{http://www.w3.org/2005/Atom}published", ns)
            if d is not None and d.text:
                pub = d.text
            else:
                d = it.find("{http://purl.org/dc/elements/1.1/}date")
                if d is not None and d.text:
                    pub = d.text
        de = it.find("description")
        if de is not None and de.text:
            desc = clean(de.text)[:200]
        else:
            de = it.find("{http://www.w3.org/2005/Atom}summary", ns)
            if de is not None and de.text:
                desc = clean(de.text)[:200]

        if not title or not link:
            continue
        articles.append({
            "title": title,
            "url": link,
            "source": source_name,
            "date": parse_date(pub),
            "snippet": desc,
            "_lang": lang,
        })
    return articles


# ============ 游戏名匹配 ============
def build_match_index(games):
    """构建 {匹配词小写: [游戏cn]} 索引。匹配词 = cn 或 en（长度>=3 避免误匹配）。"""
    idx = {}
    for track in ("a", "l", "m"):
        for g in games.get(track, []):
            cn = g.get("cn", "")
            en = g.get("en", "")
            cns = [cn] if cn else []
            for name in cns:
                if len(name) >= 2:
                    idx.setdefault(name.lower(), set()).add(cn)
            if en and len(en) >= 3:
                idx.setdefault(en.lower(), set()).add(cn)
            # 英文名的显著部分（去冒号后第一段，>=4字符）
            if en:
                parts = re.split(r"[:：\-]", en)
                for p in parts:
                    p = p.strip()
                    if len(p) >= 4:
                        idx.setdefault(p.lower(), set()).add(cn)
    return idx


def match_article(article, match_idx):
    """返回文章匹配到的游戏 cn 集合。"""
    title = (article.get("title", "") + " " + article.get("snippet", "")).lower()
    matched = set()
    for word, cns in match_idx.items():
        if word in title:
            matched.update(cns)
    return matched


# ============ Steam News ============
def fetch_steam_news(games, steam_data):
    """从 Steam News API 抓有 appid 的游戏新闻。"""
    # 构建 cn -> appid
    cn_appid = {}
    for track in ("a", "l", "m"):
        for g in games.get(track, []):
            cn = g.get("cn", "")
            en = g.get("en", "")
            appid = None
            if en and en in steam_data:
                appid = steam_data[en].get("appid")
            if not appid and cn in steam_data:
                appid = steam_data[cn].get("appid")
            if appid:
                cn_appid[cn] = appid

    results = {}  # cn -> [articles]
    for cn, appid in cn_appid.items():
        try:
            url = STEAM_NEWS_API.format(appid=appid)
            raw = http_get(url, timeout=15)
            data = json.loads(raw)
            items = data.get("appnews", {}).get("newsitems", [])
            arts = []
            for it in items[:5]:
                arts.append({
                    "title": clean(it.get("title", "")),
                    "url": f"https://store.steampowered.com/news/app/{appid}/view/{it.get('gid','')}",
                    "source": "Steam",
                    "date": datetime.fromtimestamp(it.get("date", 0), tz=__import__("datetime").timezone.utc).strftime("%Y-%m-%d") if it.get("date") else "",
                    "snippet": clean(it.get("contents", ""))[:200],
                    "_lang": "en",
                })
            if arts:
                results[cn] = arts
            time.sleep(SLEEP)
        except Exception as e:
            print(f"  [WARN] Steam News {cn} (appid {appid}): {e}")
    return results


# ============ Bing News RSS 补充（覆盖无 RSS 的中文媒体）============
def _in_news_window(game):
    """只对近期/即将发售的游戏搜 Bing（控制请求量）。"""
    import re as _re
    d = str(game.get("date") or "")
    m = _re.match(r"^(\d{4})-(\d{2})-(\d{2})", d)
    if not m:
        # 窗口期/TBA 游戏也搜（可能即将发售）
        return True
    from datetime import date as _date
    gd = _date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    today = _date.today()
    delta = (gd - today).days
    return -BING_WINDOW_PAST_DAYS <= delta <= BING_WINDOW_FUTURE_DAYS


def fetch_bing_news(games):
    """用 Bing News RSS 搜每款近期游戏的中文名，补充中文媒体报道。"""
    from datetime import timedelta
    results = {}  # cn -> [articles]
    count = 0
    for track in ("a", "l", "m"):
        for g in games.get(track, []):
            if not _in_news_window(g):
                continue
            cn = g.get("cn", "")
            if not cn or len(cn) < 2:
                continue
            try:
                q = urllib.parse.quote(cn)
                xml = http_get(BING_NEWS_RSS.format(q=q), timeout=15)
                root = ET.fromstring(xml)
                items = root.findall(".//item")
                arts = []
                for it in items[:5]:
                    t = it.find("title")
                    l = it.find("link")
                    d = it.find("pubDate")
                    de = it.find("description")
                    if t is None or l is None:
                        continue
                    # Bing 的 link 常是 apiclick 跳转，尝试解码 url= 参数
                    link = clean(l.text or "")
                    um = re.search(r"[?&]url=([^&]+)", link)
                    if um:
                        link = urllib.parse.unquote(um.group(1))
                    src = ""
                    se = it.find("source")
                    if se is not None and se.text:
                        src = clean(se.text)
                    else:
                        # 从真实链接域名推断
                        dm = re.match(r"https?://([^/]+)", link)
                        if dm:
                            src = dm.group(1).replace("www.", "")[:30]
                    arts.append({
                        "title": clean(t.text or ""),
                        "url": link,
                        "source": src or "Bing News",
                        "date": parse_date(d.text if d is not None else ""),
                        "snippet": clean(de.text if de is not None else "")[:200],
                        "_lang": "zh",
                    })
                if arts:
                    results[cn] = arts
                    count += len(arts)
                time.sleep(SLEEP)
            except Exception as e:
                print(f"  [WARN] Bing News {cn}: {str(e)[:60]}")
    print(f"Bing News 补充: {count} 篇，覆盖 {len(results)} 款游戏")
    return results


# ============ 主流程 ============
def run(commit=False, push=False):
    print(f"=== 媒体源新闻抓取 {datetime.now():%Y-%m-%d %H:%M} ===\n")

    # 1. 加载数据
    games = load_json(GAMES_JSON)
    steam_data = load_json(STEAM_JSON) if STEAM_JSON.exists() else {}
    existing_news = load_json(NEWS_JSON) if NEWS_JSON.exists() else {}
    print(f"游戏总数: a={len(games.get('a',[]))} l={len(games.get('l',[]))} m={len(games.get('m',[]))}")
    print(f"现有新闻: {len(existing_news)} 款游戏\n")

    # 2. 构建匹配索引
    match_idx = build_match_index(games)
    print(f"匹配词数: {len(match_idx)}\n")

    # 3. 抓取所有 RSS 源
    all_articles = []
    for src in RSS_SOURCES:
        try:
            print(f"  抓取 {src['name']}...", end=" ")
            xml = http_get(src["url"], timeout=20)
            arts = parse_rss(xml, src["name"], src["lang"])
            print(f"{len(arts)} 篇")
            all_articles.extend(arts)
            time.sleep(SLEEP)
        except Exception as e:
            print(f"失败: {e}")
    print(f"\nRSS 总文章数: {len(all_articles)}\n")

    # 4. Steam News
    print("抓取 Steam News...")
    steam_news = fetch_steam_news(games, steam_data)
    steam_count = sum(len(v) for v in steam_news.values())
    print(f"Steam News: {steam_count} 篇，覆盖 {len(steam_news)} 款游戏\n")

    # 5. 匹配游戏名
    new_news = {}  # cn -> [article]
    matched_total = 0
    for art in all_articles:
        cns = match_article(art, match_idx)
        for cn in cns:
            new_news.setdefault(cn, []).append(art)
            matched_total += 1
    # 加入 Steam News
    for cn, arts in steam_news.items():
        new_news.setdefault(cn, []).extend(arts)
        matched_total += len(arts)

    # 5b. Bing News 补充（覆盖无 RSS 的中文媒体：3DM/游民/17173/游侠等）
    print("抓取 Bing News 补充（中文媒体）...")
    bing_news = fetch_bing_news(games)
    for cn, arts in bing_news.items():
        # Bing 搜的就是游戏名，直接关联；但需过滤标题不含游戏名的误匹配
        for a in arts:
            if cn.lower() in (a.get("title", "") + a.get("snippet", "")).lower():
                new_news.setdefault(cn, []).append(a)
                matched_total += 1
    print(f"匹配到游戏的新闻: {matched_total} 篇，覆盖 {len(new_news)} 款游戏\n")

    # 6. 合并到现有 news（每游戏保留最新 MAX_PER_GAME 条，按日期降序，按 url 去重）
    merged = dict(existing_news)  # 保留已有的
    report = {"new": 0, "updated": 0, "unchanged": 0}
    for cn, arts in new_news.items():
        # 合并已有 + 新增，按 url 去重
        existing = merged.get(cn, [])
        url_set = {a["url"] for a in existing}
        combined = list(existing)
        added = 0
        for a in arts:
            # 清理临时字段
            a_clean = {k: v for k, v in a.items() if not k.startswith("_")}
            if a_clean["url"] not in url_set:
                combined.append(a_clean)
                url_set.add(a_clean["url"])
                added += 1
        # 按日期降序排序
        combined.sort(key=lambda x: x.get("date", ""), reverse=True)
        # 截断到 MAX_PER_GAME
        before = len(combined)
        combined = combined[:MAX_PER_GAME]
        merged[cn] = combined
        if added > 0:
            report["updated"] += 1
            report["new"] += added
        else:
            report["unchanged"] += 1

    print(f"合并结果: 新增 {report['new']} 篇，更新 {report['updated']} 款，未变 {report['unchanged']} 款\n")

    # 6b. 翻译非中文标题（Google Translate 免费接口）
    translate_count = 0
    skip_count = 0
    print("翻译非中文标题...")
    for cn, arts in merged.items():
        for a in arts:
            # 跳过已有翻译的、已是中文的
            if a.get("title_cn"):
                skip_count += 1
                continue
            title = a.get("title", "")
            if not title or is_chinese(title):
                continue
            # 调 Google Translate
            translated = translate_title(title)
            if translated:
                a["title_cn"] = translated
                translate_count += 1
                time.sleep(TRANSLATE_SLEEP)
            else:
                skip_count += 1
    print(f"翻译完成: 新翻译 {translate_count} 条，跳过 {skip_count} 条\n")

    # 7. 写回 news.json
    save_json(NEWS_JSON, merged)
    print(f"已写入 {NEWS_JSON}")

    # 8. 写回 index.html 内联 GAME_NEWS
    with open(INDEX, "r", encoding="utf-8") as f:
        c = f.read()
    pos = c.find("const GAME_NEWS")
    if pos < 0:
        print("[WARN] index.html 中未找到 GAME_NEWS")
    else:
        brace_start = c.find("{", pos)
        i = brace_start + 1
        depth = 1
        while i < len(c) and depth > 0:
            if c[i] == "{":
                depth += 1
            elif c[i] == "}":
                depth -= 1
            i += 1
        while i < len(c) and c[i] in (";", " ", "\n", "\r", "\t"):
            i += 1
        new_inline = "const GAME_NEWS = " + js_spaced(merged) + ";\n"
        c = c[:pos] + new_inline + c[i:]
        with open(INDEX, "w", encoding="utf-8") as f:
            f.write(c)
        print(f"已更新 {INDEX} 内联 GAME_NEWS")

    # 9. 输出报告
    print("\n=== 抓取报告 ===")
    print(f"RSS 源: {len(RSS_SOURCES)} 个，文章 {len(all_articles)} 篇")
    print(f"Steam News: {steam_count} 篇")
    print(f"Bing News 补充: {sum(len(v) for v in bing_news.values())} 篇")
    print(f"匹配游戏: {len(new_news)} 款")
    print(f"合并后: 新增 {report['new']} 篇，涉及 {report['updated']} 款游戏")
    print(f"新闻总条数: {sum(len(v) for v in merged.values())}")
    print(f"有新闻的游戏数: {len(merged)}")

    # 10. 可选 commit / push
    if commit:
        import subprocess
        print("\n=== Git commit ===")
        subprocess.run(["git", "add", str(NEWS_JSON), str(INDEX)], cwd=ROOT)
        msg = f"news: media-source refresh {datetime.now():%Y-%m-%d} (+{report['new']} articles)"
        subprocess.run(["git", "commit", "-m", msg], cwd=ROOT)
        if push:
            print("=== Git push ===")
            subprocess.run(["git", "push"], cwd=ROOT)

    return {"merged": merged, "report": report}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--commit", action="store_true")
    ap.add_argument("--push", action="store_true")
    args = ap.parse_args()
    run(commit=args.commit, push=args.push)
