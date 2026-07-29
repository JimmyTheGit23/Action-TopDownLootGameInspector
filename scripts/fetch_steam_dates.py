# -*- coding: utf-8 -*-
"""overrides 之外游戏的发售日用 Steam 商店页面校对。

注：appdetails API 在本机出口被限流（全量返回 null），改为抓商店页 HTML
中的 <div class="date">，带年龄门 cookie。

规则：
- Steam 精度 >= 本地精度才自动更新（TBA/窗口 → 定档是升级；day → day 日期变化算变更）
- Steam 信息比本地粗（如本地已有确切日期，Steam 只有年份）→ 不动，仅记录
- 与本地日期相差 <=1 天视为时区噪音，保留本地并记录
- overrides.json 里列出的游戏完全跳过
"""
import re
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (  # noqa: E402
    DATA, OUT_DIR, ROOT, load_json, save_json, http_get, clean,
    parse_steam_date, m_frac_day, m_frac_window, quarter_of_month,
    local_rank, RANK,
)

STORE_PAGE = "https://store.steampowered.com/app/{appid}/?cc=us&l=en"
AGE_COOKIE = {"Cookie": "birthtime=568022401; mature_content=1"}
SLEEP = 1.0


def fetch_release(appid):
    """抓商店页，返回 {'date': 原始日期串}；页面无效返回 None。"""
    html = http_get(STORE_PAGE.format(appid=appid), headers=AGE_COOKIE)
    m = re.search(r'<div class="date">([^<]*)</div>', html)
    if not m:
        return None
    return {"date": clean(m.group(1))}


def apply_update(game, kind, info, steam_raw):
    """把 Steam 解析结果写入游戏条目，返回变更描述。"""
    old = f"{game.get('date')}(precision={game.get('_precision')})"
    if kind == "day":
        y, m, d = info
        iso = f"{y:04d}-{m:02d}-{d:02d}"
        game["year"] = str(y)
        game["window"] = quarter_of_month(m)
        game["date_raw"] = iso
        game["date"] = iso
        game["_m_frac"] = m_frac_day(y, m, d)
        game["_precision"] = "day"
    elif kind == "month":
        y, m = info
        game["year"] = str(y)
        game["window"] = quarter_of_month(m)
        game["date_raw"] = steam_raw
        game["date"] = f"{y:04d}-{m:02d}"
        game["_m_frac"] = m_frac_window(y, quarter_of_month(m))
        game["_precision"] = "window"
    elif kind == "quarter":
        y, q = info
        game["year"] = str(y)
        game["window"] = f"Q{q}"
        game["date_raw"] = steam_raw
        game["date"] = f"{y} Q{q}"
        game["_m_frac"] = m_frac_window(y, f"Q{q}")
        game["_precision"] = "window"
    elif kind == "year":
        (y,) = info
        game["year"] = str(y)
        game["window"] = "年内 Within the Year"
        game["date_raw"] = steam_raw
        game["date"] = f"{y} 年内"
        game["_m_frac"] = m_frac_window(y, "年内")
        game["_precision"] = "window"
    return f"{old} -> {game['date']}"


def run():
    games = load_json(DATA / "games.json")
    apps = load_json(DATA / "steam_apps.json")
    overrides = (load_json(ROOT / "scripts" / "overrides.json")).get("games", {})

    report = {"time": datetime.now().isoformat(timespec="seconds"),
              "changed": [], "kept_more_precise": [], "unchanged": 0,
              "tolerance_1day": [], "tba_on_steam": [], "no_appid": [],
              "overridden": [], "errors": []}

    for track in ("a", "l", "m"):
        for g in games.get(track, []):
            cn = g.get("cn", "")
            if cn in overrides:
                report["overridden"].append(cn)
                continue
            appid = apps.get(cn) or apps.get(clean(g.get("en")))
            if not appid:
                report["no_appid"].append(cn)
                continue
            try:
                rd = fetch_release(appid)
            except Exception as e:  # noqa: BLE001
                report["errors"].append({"cn": cn, "appid": appid, "error": str(e)})
                continue
            finally:
                time.sleep(SLEEP)
            if rd is None:
                report["errors"].append({"cn": cn, "appid": appid, "error": "no date div (invalid page?)"})
                continue
            kind, info = parse_steam_date(rd["date"])
            if kind in ("tba", "unknown"):
                report["tba_on_steam"].append({"cn": cn, "steam_date": rd["date"]})
                continue
            if kind == "day":
                iso = f"{info[0]:04d}-{info[1]:02d}-{info[2]:02d}"
                if g.get("_precision") == "day":
                    if g.get("date") == iso:
                        report["unchanged"] += 1
                        continue
                    try:
                        d_local = datetime.strptime(g.get("date"), "%Y-%m-%d")
                        d_steam = datetime(*info)
                        if abs((d_steam - d_local).days) <= 1:
                            report["tolerance_1day"].append(
                                {"cn": cn, "local": g.get("date"), "steam": iso})
                            continue
                    except (ValueError, TypeError):
                        pass
            else:
                if kind == "month":
                    canonical = f"{info[0]:04d}-{info[1]:02d}"
                elif kind == "quarter":
                    canonical = f"{info[0]} Q{info[1]}"
                else:
                    canonical = f"{info[0]} 年内"
                if g.get("date") == canonical:
                    report["unchanged"] += 1
                    continue
                if RANK[kind] <= local_rank(g):
                    report["kept_more_precise"].append(
                        {"cn": cn, "local": g.get("date"), "steam": rd["date"]})
                    continue
            desc = apply_update(g, kind, info, rd["date"])
            report["changed"].append({"cn": cn, "appid": appid, "change": desc,
                                      "steam_raw": rd["date"]})

    save_json(DATA / "games.json", games, pretty=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    save_json(OUT_DIR / f"steam_report_{ts}.json", report, pretty=True)
    save_json(OUT_DIR / "steam_report_latest.json", report, pretty=True)

    print(f"[steam] changed={len(report['changed'])} unchanged={report['unchanged']} "
          f"kept_local={len(report['kept_more_precise'])} ±1day={len(report['tolerance_1day'])} "
          f"tba={len(report['tba_on_steam'])} no_appid={len(report['no_appid'])} "
          f"overridden={len(report['overridden'])} errors={len(report['errors'])}")
    for c in report["changed"]:
        print(f"  * {c['cn']}: {c['change']}  (steam: {c['steam_raw']})")
    for t in report["tolerance_1day"]:
        print(f"  ~ {t['cn']}: local {t['local']} vs steam {t['steam']} (±1天，保留本地)")
    for e in report["errors"]:
        print(f"  ! {e['cn']} (appid {e['appid']}): {e['error']}")
    return report


if __name__ == "__main__":
    run()
