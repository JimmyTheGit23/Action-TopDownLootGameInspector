# -*- coding: utf-8 -*-
"""把 docs/data/*.json 重新内联进 docs/index.html，并同步生成 min/inline 产物。

替换目标（index.html 中各恰好一行）：
  const GAMES = {...};
  const STEAM_APPS={...};
  const GAME_NEWS = {...};
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DATA, INDEX, load_json, save_json, js_min, js_spaced  # noqa: E402

# 头部不带时间戳：避免数据未变时产生无意义 diff，--commit 只在真有变更时提交
GAMES_INLINE_HEADER = "// 游戏数据 · 自动生成（scripts/build_inline.py）\n"
NEWS_INLINE_HEADER = "// 游戏新闻数据 · 自动生成（scripts/build_inline.py）\n"


def replace_once(html, pattern, repl):
    new, n = re.subn(pattern, repl, html, count=0, flags=re.M)
    if n != 1:
        raise RuntimeError(f"pattern matched {n} times (expect 1): {pattern}")
    return new


def run():
    games = load_json(DATA / "games.json")
    news = load_json(DATA / "news.json")
    apps = load_json(DATA / "steam_apps.json")

    games_js = "const GAMES = " + js_min(games) + ";"
    apps_js = "const STEAM_APPS=" + js_min(apps) + ";"
    news_js = "const GAME_NEWS = " + js_spaced(news) + ";"

    save_json(DATA / "games.min.json", games, pretty=False)
    with open(DATA / "games_inline.js", "w", encoding="utf-8") as f:
        f.write(GAMES_INLINE_HEADER + games_js + "\n")
    with open(DATA / "news_inline.js", "w", encoding="utf-8") as f:
        f.write(NEWS_INLINE_HEADER + news_js + "\n")

    html = INDEX.read_text(encoding="utf-8")
    html = replace_once(html, r"^const GAMES = .*;$", lambda m: games_js)
    html = replace_once(html, r"^const STEAM_APPS=.*;$", lambda m: apps_js)
    html = replace_once(html, r"^const GAME_NEWS = .*;$", lambda m: news_js)
    INDEX.write_text(html, encoding="utf-8")
    print(f"[build] index.html inlined: games={len(games_js)}B apps={len(apps_js)}B news={len(news_js)}B")


if __name__ == "__main__":
    run()
