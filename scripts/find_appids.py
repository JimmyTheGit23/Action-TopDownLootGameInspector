# -*- coding: utf-8 -*-
"""给没有 appid 的游戏在 Steam 上搜索候选 appid。

用法：
  python scripts/find_appids.py            # 扫描全部赛道无 appid 游戏
  python scripts/find_appids.py --write    # 把高置信匹配写入 steam_apps.json

匹配规则（保守）：
- 英文名（无英文名的用中文名）在 Steam 搜索建议中取前 5 个候选
- 归一化后完全相等 / 一方包含另一方 → high；否则仅列出候选人工确认
"""
import argparse
import json
import re
import sys
import time
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DATA, load_json, save_json, http_get, clean  # noqa: E402

SUGGEST = "https://store.steampowered.com/search/suggest?term={q}&f=games&cc=us&realm=1&l=en"
SLEEP = 0.8


def norm(s):
    s = (s or "").lower()
    s = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", s)
    return s


def search_steam(name):
    body = http_get(SUGGEST.format(q=urllib.parse.quote(name)), timeout=12, retries=1)
    out = []
    for m in re.finditer(r'data-ds-appid="(\d+)"[^>]*>.*?<div class="match_name">([^<]+)</div>',
                         body, re.S):
        out.append((int(m.group(1)), clean(m.group(2))))
    if not out:  # suggest 无结果时可能是地区限制，尝试页面搜索结果
        for m in re.finditer(r'data-ds-appid="(\d+)".*?<span class="title">([^<]+)</span>',
                             body, re.S):
            out.append((int(m.group(1)), clean(m.group(2))))
    return out[:5]


def score(query, cand):
    nq, nc = norm(query), norm(cand)
    if not nq or not nc:
        return "low"
    if nq == nc:
        return "high"
    if nq in nc or nc in nq:
        shorter = min(len(nq), len(nc))
        longer = max(len(nq), len(nc))
        return "high" if shorter / longer >= 0.6 else "mid"
    return "low"


def run(write=False):
    games = load_json(DATA / "games.json")
    apps = load_json(DATA / "steam_apps.json")
    ovr_path = Path(__file__).resolve().parent / "overrides.json"
    overrides = load_json(ovr_path).get("games", {}) if ovr_path.exists() else {}

    proposals, manual, notfound = [], [], []
    for track in ("a", "l", "m"):
        for g in games.get(track, []):
            cn = g.get("cn", "")
            if cn in overrides:
                continue
            if cn in apps or clean(g.get("en")) in apps:
                continue
            query = clean(g.get("en")) or cn
            try:
                cands = search_steam(query)
            except Exception as e:  # noqa: BLE001
                print(f"  ! {cn}: search failed {e}")
                time.sleep(SLEEP)
                continue
            time.sleep(SLEEP)
            if not cands:
                notfound.append(cn)
                continue
            best_appid, best_name, best_score = None, None, "low"
            for appid, name in cands:
                s = score(query, name)
                if s == "high":
                    best_appid, best_name, best_score = appid, name, s
                    break
                if s == "mid" and best_score == "low":
                    best_appid, best_name, best_score = appid, name, s
            if best_score == "high":
                proposals.append({"cn": cn, "track": track, "appid": best_appid,
                                  "steam_name": best_name, "score": best_score})
            else:
                manual.append({"cn": cn, "query": query,
                               "cands": [{"appid": a, "name": n,
                                          "score": score(query, n)} for a, n in cands]})

    print(f"[find] high={len(proposals)} manual={len(manual)} notfound={len(notfound)}")
    for p in proposals:
        mark = "WRITE" if write else "    "
        print(f"  + [{p['track']}] {p['cn']} -> {p['appid']} ({p['steam_name']}) {mark}")
    for m in manual:
        cands = " | ".join(f"{c['appid']}:{c['name']}({c['score']})" for c in m["cands"])
        print(f"  ? {m['cn']} [{m['query']}] 候选: {cands}")

    if write and proposals:
        for p in proposals:
            apps[p["cn"]] = p["appid"]
        save_json(DATA / "steam_apps.json", apps, pretty=True)
        print(f"[find] wrote {len(proposals)} appids -> docs/data/steam_apps.json")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    run(write=args.write)
