# -*- coding: utf-8 -*-
"""抓取 MMO 手游的 iOS 中国区畅销榜/免费榜排名。

数据源（Apple 官方，无需 key）：
  1. iTunes Search API  → 确认 App ID（预设映射 + 自动搜索）
  2. AppStore RSS 畅销榜 CN（topgrossingapplications/limit=100）
  3. AppStore RSS 免费榜 CN（topfreeapplications/limit=100）

输出：docs/data/ios_stats.json + index.html 内联 IOS_STATS
峰值排名：与上次数据比较取历史最高（数值越小排名越高）

DAU/累计流水/注册用户：Apple API 无此数据，预留字段供手动录入（overrides.json）

用法：
  python fetch_ios_stats.py
"""
import json
import sys
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DATA, INDEX, load_json, save_json, http_get, clean, js_spaced  # noqa: E402

IOS_STATS_JSON = DATA / "ios_stats.json"
OVERRIDES_JSON = Path(__file__).resolve().parent / "ios_overrides.json"

# 预设 App ID 映射（从 iTunes Search 确认，避免每次搜索）
IOS_APPIDS = {
    "梦幻西游手游": 940547441,
    "逆水寒手游→新世界": 1541570980,
    "地下城与勇士：起源": 1529851592,
    "倩女幽魂手游": 1033387365,
    "一梦江湖": 1089795423,
    "大话西游手游": 1015364140,
    "天堂2：盟约": 6739202341,
    "问道手游": 1031897589,
    "杖剑传说": 6473333072,
    "宗师之上": 6755095931,
    "天涯明月刀手游": 1438499417,
    "冒险岛枫之传说": 6447610302,
    "斗罗大陆：猎魂世界（海外版）": 6739239402,
    "RO仙境传说3（RO3）": 1071801856,  # 暂用 ROM1，ROM3 未上线
    # 以下暂无准确 App ID（搜索匹配错误，待手动确认）
    # "梦幻新诛仙：轻享": ???,
    # "仙境传说RO:守护永恒的爱2（ROM2/守爱2）": ???,  # ROM2 未上线
    # "命运方舟2（失落的方舟手游）": ???,  # 未上线
}

GROSSING_RSS = "https://itunes.apple.com/cn/rss/topgrossingapplications/limit=100/json"
FREE_RSS = "https://itunes.apple.com/cn/rss/topfreeapplications/limit=100/json"


def parse_chart(json_text):
    """解析 AppStore RSS 榜单 JSON，返回 {app_id: rank} 字典（rank 从1开始）。"""
    d = json.loads(json_text)
    entries = d.get("feed", {}).get("entry", [])
    chart = {}
    for i, entry in enumerate(entries, 1):
        app_id = entry.get("id", {}).get("attributes", {}).get("im:id", "")
        name = entry.get("im:name", {}).get("label", "")
        if app_id:
            chart[app_id] = {"rank": i, "name": name}
    return chart


def run():
    print(f"=== iOS 手游榜单抓取 {datetime.now():%Y-%m-%d %H:%M} ===\n")

    # 1. 抓畅销榜 + 免费榜
    print("抓取 AppStore 中国区畅销榜...", end=" ")
    grossing = parse_chart(http_get(GROSSING_RSS, timeout=20))
    print(f"{len(grossing)} 款")
    print("抓取 AppStore 中国区免费榜...", end=" ")
    free = parse_chart(http_get(FREE_RSS, timeout=20))
    print(f"{len(free)} 款\n")

    # 2. 读取现有数据（保留历史峰值）
    existing = load_json(IOS_STATS_JSON) if IOS_STATS_JSON.exists() else {}

    # 3. 读取手动 overrides（DAU/流水/注册用户）
    overrides = load_json(OVERRIDES_JSON) if OVERRIDES_JSON.exists() else {}

    # 4. 匹配每款手游
    results = {}
    in_chart_count = 0
    for cn, appid in IOS_APPIDS.items():
        appid_str = str(appid)
        rank_g = grossing.get(appid_str, {}).get("rank")
        rank_f = free.get(appid_str, {}).get("rank")
        name_on_chart = grossing.get(appid_str, {}).get("name") or free.get(appid_str, {}).get("name", "")

        # 峰值：与历史数据比较（取数值更小=排名更高的）
        prev = existing.get(cn, {})
        peak_g = rank_g if rank_g else prev.get("rank_grossing_peak")
        if prev.get("rank_grossing_peak") and peak_g:
            peak_g = min(peak_g, prev["rank_grossing_peak"])
        peak_f = rank_f if rank_f else prev.get("rank_free_peak")
        if prev.get("rank_free_peak") and peak_f:
            peak_f = min(peak_f, prev["rank_free_peak"])

        entry = {
            "app_id": appid,
            "app_name": name_on_chart or cn,
            "rank_grossing": rank_g,  # None = 不在榜
            "rank_free": rank_f,
            "rank_grossing_peak": peak_g,
            "rank_free_peak": peak_f,
            "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        }
        # 合并手动 overrides
        if cn in overrides:
            entry.update(overrides[cn])
        # 保留历史 overrides 字段
        for k in ("dau", "revenue_total", "registrations", "revenue_note"):
            if k in prev and k not in entry:
                entry[k] = prev[k]

        results[cn] = entry
        status = ""
        if rank_g:
            status += f"畅销#{rank_g} "
            in_chart_count += 1
        if rank_f:
            status += f"免费#{rank_f} "
            in_chart_count += 1
        if not status:
            status = "不在榜"
        print(f"  {cn:<30} appid={appid}  {status}")

    print(f"\n在榜游戏: {in_chart_count} 款\n")

    # 5. 写 ios_stats.json
    save_json(IOS_STATS_JSON, results)
    print(f"已写入 {IOS_STATS_JSON}")

    # 6. 写 index.html 内联 IOS_STATS
    with open(INDEX, "r", encoding="utf-8") as f:
        c = f.read()
    new_inline = "const IOS_STATS = " + js_spaced(results) + ";\n"
    pos = c.find("const IOS_STATS")
    if pos >= 0:
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
        # 新增：插在 STEAM_STATS 之后
        ss_semi = c.find(";", c.find("const STEAM_STATS"))
        insert_at = c.find("\n", ss_semi) + 1
        c = c[:insert_at] + new_inline + c[insert_at:]
    with open(INDEX, "w", encoding="utf-8") as f:
        f.write(c)
    print(f"已更新 {INDEX} 内联 IOS_STATS ({len(results)} 款)")

    # 7. 报告
    print("\n=== 抓取报告 ===")
    print(f"追踪手游: {len(IOS_APPIDS)} 款")
    print(f"在畅销榜: {sum(1 for v in results.values() if v.get('rank_grossing'))} 款")
    print(f"在免费榜: {sum(1 for v in results.values() if v.get('rank_free'))} 款")
    has_manual = sum(1 for v in results.values() if v.get("dau") or v.get("revenue_total"))
    print(f"有手动数据(DAU/流水): {has_manual} 款")
    return results


if __name__ == "__main__":
    run()
