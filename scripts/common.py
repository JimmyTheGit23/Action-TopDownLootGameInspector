# -*- coding: utf-8 -*-
"""公共工具：路径、JSON IO、HTTP、Steam 日期解析、_m_frac 计算。"""
import json
import re
import time
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime, date

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
DATA = DOCS / "data"
INDEX = DOCS / "index.html"
OUT_DIR = ROOT / "scripts" / "out"
OUT_DIR.mkdir(parents=True, exist_ok=True)

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path, obj, pretty=True):
    with open(path, "w", encoding="utf-8") as f:
        if pretty:
            json.dump(obj, f, ensure_ascii=False, indent=2)
        else:
            json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")


def js_min(obj):
    """GAMES 风格：无空格压缩。已转义 </ 防止内联脚本截断。"""
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def js_spaced(obj):
    """GAME_NEWS 风格：默认分隔符（带空格），与现有内联格式一致。"""
    return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")


def http_get(url, timeout=15, retries=2, encoding="utf-8", headers=None):
    last = None
    hdrs = {"User-Agent": UA}
    if headers:
        hdrs.update(headers)
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=hdrs)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
            return raw.decode(encoding, errors="replace")
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(1.5 * (attempt + 1))
    raise last


def clean(s):
    return re.sub(r"\s+", " ", str(s or "")).strip()


# ---------------- Steam 日期解析 ----------------

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

# 精度等级：数值越大越精确。自动更新只允许同级变更或升级，禁止降级。
RANK = {"tba": 0, "year": 1, "half": 1.5, "quarter": 2, "month": 2.5, "day": 3}


def parse_steam_date(s):
    """解析 Steam 英文日期串，返回 (kind, info)。
    kind: day|month|quarter|year|tba|unknown
    info: day→(y,m,d)  month→(y,m)  quarter→(y,q)  year→(y,)  其他→None
    """
    t = clean(s)
    if not t:
        return ("tba", None)
    low = t.lower()
    if any(k in low for k in ("coming soon", "to be announced", "tbd", "tba", "soon")):
        return ("tba", None)
    m = re.match(r"^([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})$", t)          # Oct 29, 2026
    if m and m.group(1)[:3].lower() in _MONTHS:
        return ("day", (int(m.group(3)), _MONTHS[m.group(1)[:3].lower()], int(m.group(2))))
    m = re.match(r"^(\d{1,2})\s+([A-Za-z]+),?\s*(\d{4})$", t)          # 29 Oct, 2026
    if m and m.group(2)[:3].lower() in _MONTHS:
        return ("day", (int(m.group(3)), _MONTHS[m.group(2)[:3].lower()], int(m.group(1))))
    m = re.match(r"^([A-Za-z]+)\s+(\d{4})$", t)                        # Oct 2026
    if m and m.group(1)[:3].lower() in _MONTHS:
        return ("month", (int(m.group(2)), _MONTHS[m.group(1)[:3].lower()]))
    m = re.match(r"^Q([1-4])\s+(\d{4})$", t)                           # Q4 2026
    if m:
        return ("quarter", (int(m.group(2)), int(m.group(1))))
    m = re.match(r"^(\d{4})$", t)                                      # 2027
    if m:
        return ("year", (int(m.group(1)),))
    return ("unknown", None)


# ---------------- _m_frac / window 计算 ----------------
# 约定（与现有数据一致）：2026-01 为 0 的绝对月份索引 + 月内偏移。
# day: idx + (day-1)/30；Q1..Q4: idx+0.5/3.5/6.5/9.5；H1/H2: idx+2.5/8.5；年内: idx+9.5

def m_frac_day(y, m, d):
    return round((y - 2026) * 12 + (m - 1) + (d - 1) / 30.0, 8)


def m_frac_window(y, label):
    idx = (y - 2026) * 12
    if label.startswith("Q") and len(label) == 2:
        return idx + {"Q1": 0.5, "Q2": 3.5, "Q3": 6.5, "Q4": 9.5}[label]
    if label == "H1":
        return idx + 2.5
    if label == "H2":
        return idx + 8.5
    return idx + 9.5  # 年内


def quarter_of_month(m):
    return "Q" + str((m - 1) // 3 + 1)


def local_rank(game):
    """现有条目的精度等级，用于禁止自动降级。"""
    p = game.get("_precision")
    if p == "day":
        return RANK["day"]
    if p == "tba":
        return RANK["tba"]
    d = str(game.get("date") or "")
    if re.match(r"^\d{4}-\d{2}$", d):
        return RANK["month"]
    if "Q" in d:
        return RANK["quarter"]
    if re.search(r"H[12]", d):
        return RANK["half"]
    return RANK["year"]  # 年内 等
