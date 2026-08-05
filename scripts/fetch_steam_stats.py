# -*- coding: utf-8 -*-
"""从 Steam 官方 API 抓取已上线游戏的评价、价格（美区/中国区）、当前在线人数(CCU)。

数据源（全部 Steam 官方，无需 key）：
  1. appreviews API    → 评价（好评/差评/总数/描述）
  2. appdetails API    → 价格（cc=us 美区 + cc=cn 中国区）
  3. GetNumberOfCurrentPlayers API → CCU

输出：docs/data/steam_stats.json + index.html 内联 STEAM_STATS
只覆盖 STEAM_APPS 里有 appid 的游戏。

用法：
  python fetch_steam_stats.py
"""
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DATA, INDEX, load_json, save_json, http_get, clean, js_spaced  # noqa: E402

STEAM_STATS_JSON = DATA / "steam_stats.json"
SLEEP = 0.4  # 避免 Steam 限流

APPREVIEWS_API = "https://store.steampowered.com/appreviews/{appid}?json=1&language=all&purchase_type=all&num_per_page=0"
APPDETAILS_API = "https://store.steampowered.com/api/appdetails?appids={appid}&l=schinese&cc={cc}"
CCU_API = "https://api.steampowered.com/ISteamUserStats/GetNumberOfCurrentPlayers/v1/?appid={appid}"


def fetch_review(appid):
    """评价：好评/差评/总数/描述。"""
    try:
        raw = http_get(APPREVIEWS_API.format(appid=appid), timeout=15)
        d = json.loads(raw)
        q = d.get("query_summary", {})
        return {
            "positive": q.get("total_positive", 0),
            "negative": q.get("total_negative", 0),
            "total": q.get("total_reviews", 0),
            "desc": q.get("review_score_desc", ""),
            "score": q.get("review_score", 0),
        }
    except Exception as e:
        print(f"    [WARN] review {appid}: {str(e)[:60]}")
        return None


def fetch_price(appid, cc):
    """价格：final_formatted / initial_formatted / discount_percent。"""
    try:
        raw = http_get(APPDETAILS_API.format(appid=appid, cc=cc), timeout=15)
        d = json.loads(raw)
        key = str(appid)
        if key not in d or not d[key].get("success"):
            return None
        data = d[key].get("data", {})
        # data 可能是 dict（正常）或 list（异常情况）
        if isinstance(data, list):
            data = data[0] if data else {}
        if not isinstance(data, dict):
            return None
        po = data.get("price_overview")
        if not po:
            return None  # 免费游戏或无价格
        return {
            "final": po.get("final_formatted", ""),
            "initial": po.get("initial_formatted", ""),
            "discount": po.get("discount_percent", 0),
        }
    except Exception as e:
        print(f"    [WARN] price {appid} cc={cc}: {str(e)[:60]}")
        return None


def fetch_ccu(appid):
    """当前在线人数。"""
    try:
        raw = http_get(CCU_API.format(appid=appid), timeout=15)
        d = json.loads(raw)
        return d.get("response", {}).get("player_count", 0)
    except Exception as e:
        print(f"    [WARN] ccu {appid}: {str(e)[:60]}")
        return None


def run():
    print(f"=== Steam 数据抓取（评价/价格/CCU）{datetime.now():%Y-%m-%d %H:%M} ===\n")

    # 1. 读取 STEAM_APPS（从 index.html 内联）
    with open(INDEX, "r", encoding="utf-8") as f:
        c = f.read()
    start = c.find("const STEAM_APPS={")
    if start < 0:
        start = c.find("const STEAM_APPS = {")
    semi = c.find(";", start)
    brace_start = c.find("{", start)
    brace_end = c.rfind("}", start, semi)
    steam_apps = json.loads(c[brace_start:brace_end + 1])
    print(f"STEAM_APPS: {len(steam_apps)} 款游戏有 appid\n")

    # 2. 读取现有 steam_stats（保留上次抓取时间做对比）
    existing = load_json(STEAM_STATS_JSON) if STEAM_STATS_JSON.exists() else {}

    # 3. 逐个抓取
    results = {}
    ok = 0
    fail = 0
    for i, (cn, appid) in enumerate(steam_apps.items(), 1):
        print(f"  [{i}/{len(steam_apps)}] {cn} (appid {appid})...", end=" ")
        try:
            review = fetch_review(appid)
            time.sleep(SLEEP)
            price_cn = fetch_price(appid, "cn")
            time.sleep(SLEEP)
            price_us = fetch_price(appid, "us")
            time.sleep(SLEEP)
            ccu = fetch_ccu(appid)
            time.sleep(SLEEP)

            if review is None and price_cn is None and price_us is None and ccu is None:
                print("全部失败，跳过")
                fail += 1
                continue

            entry = {
                "appid": appid,
                "review": review,
                "price_cn": price_cn,
                "price_us": price_us,
                "ccu": ccu,
                "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            }
            results[cn] = entry
            # 简要输出
            r_desc = review["desc"] if review else "—"
            p_cn = price_cn["final"] if price_cn else "—"
            p_us = price_us["final"] if price_us else "—"
            print(f"评价={r_desc} 价格CN={p_cn} 价格US={p_us} CCU={ccu}")
            ok += 1
        except Exception as e:
            print(f"失败: {str(e)[:60]}")
            fail += 1

    print(f"\n抓取完成: 成功 {ok}，失败 {fail}\n")

    # 4. 写 steam_stats.json
    save_json(STEAM_STATS_JSON, results)
    print(f"已写入 {STEAM_STATS_JSON}")

    # 5. 写 index.html 内联 STEAM_STATS
    with open(INDEX, "r", encoding="utf-8") as f:
        c = f.read()
    new_inline = "const STEAM_STATS = " + js_spaced(results) + ";\n"
    pos = c.find("const STEAM_STATS")
    if pos >= 0:
        # 替换现有
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
        c = c[:pos] + new_inline + c[i:]
    else:
        # 新增：插在 STEAM_APPS 行之后
        sa_semi = c.find(";", c.find("const STEAM_APPS"))
        insert_at = c.find("\n", sa_semi) + 1
        c = c[:insert_at] + new_inline + c[insert_at:]
    with open(INDEX, "w", encoding="utf-8") as f:
        f.write(c)
    print(f"已更新 {INDEX} 内联 STEAM_STATS ({len(results)} 款)")

    # 6. 报告
    print("\n=== 抓取报告 ===")
    print(f"总游戏: {len(steam_apps)}，成功: {ok}，失败: {fail}")
    reviewed = sum(1 for v in results.values() if v.get("review"))
    priced = sum(1 for v in results.values() if v.get("price_cn") or v.get("price_us"))
    ccu_ok = sum(1 for v in results.values() if (v.get("ccu") or 0) > 0)
    print(f"有评价: {reviewed}，有价格: {priced}，有CCU: {ccu_ok}")
    return results


if __name__ == "__main__":
    run()
