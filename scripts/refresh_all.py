# -*- coding: utf-8 -*-
"""每周刷新编排：Steam 日期校对 → 新闻刷新 → 重新内联 → 可选提交/推送。

用法：
  python refresh_all.py                 # 只刷新数据，输出周报
  python refresh_all.py --commit        # 刷新 + 本地提交
  python refresh_all.py --commit --push # 刷新 + 提交 + 推送（GitHub Pages 自动部署）
"""
import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import OUT_DIR, ROOT  # noqa: E402
import build_inline  # noqa: E402
import fetch_news  # noqa: E402
import fetch_steam_dates  # noqa: E402


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--commit", action="store_true")
    ap.add_argument("--push", action="store_true")
    ap.add_argument("--skip-steam", action="store_true")
    ap.add_argument("--skip-news", action="store_true")
    ap.add_argument("--news-max-games", type=int, default=None)
    args = ap.parse_args()

    steam_rep = news_rep = None
    if not args.skip_steam:
        steam_rep = fetch_steam_dates.run()
    if not args.skip_news:
        news_rep = fetch_news.run(max_games=args.news_max_games)
    build_inline.run()

    lines = [f"# 每周刷新报告 {datetime.now():%Y-%m-%d %H:%M}", ""]
    if steam_rep:
        lines.append(f"## Steam 发售日校对：变更 {len(steam_rep['changed'])} 项")
        for c in steam_rep["changed"]:
            lines.append(f"- {c['cn']}: {c['change']}")
        if steam_rep["errors"]:
            lines.append(f"### 抓取失败 {len(steam_rep['errors'])} 项")
            for e in steam_rep["errors"]:
                lines.append(f"- {e['cn']} (appid {e.get('appid')}): {e['error']}")
        lines.append(f"（无 appid {len(steam_rep['no_appid'])} 个 / override 跳过 "
                     f"{len(steam_rep['overridden'])} 个 / Steam 仍 TBA "
                     f"{len(steam_rep['tba_on_steam'])} 个）")
        lines.append("")
    if news_rep:
        lines.append(f"## 新闻刷新：{news_rep['fetched']} 个游戏，新增 {news_rep['new_items']} 条")
        if news_rep["errors"]:
            lines.append(f"### 失败 {len(news_rep['errors'])} 项")
            for e in news_rep["errors"][:10]:
                lines.append(f"- {e['cn']}: {e['error']}")
    text = "\n".join(lines)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    (OUT_DIR / f"refresh_{ts}.md").write_text(text, encoding="utf-8")
    (OUT_DIR / "refresh_latest.md").write_text(text, encoding="utf-8")
    print("\n" + text)

    if args.commit:
        git("add", "-A")
        diff = git("diff", "--cached", "--stat")
        if not diff.stdout.strip():
            print("\n[git] 无变更，跳过提交")
            return
        n_changes = len(steam_rep["changed"]) if steam_rep else 0
        msg = f"chore(data): weekly refresh {datetime.now():%Y-%m-%d} — {n_changes} date changes"
        r = git("commit", "-m", msg)
        print("\n[git] commit:", r.stdout.strip() or r.stderr.strip())
        if args.push:
            r = git("push")
            print("[git] push:", r.stdout.strip() or r.stderr.strip())


if __name__ == "__main__":
    main()
