# 动作游戏看板每周刷新 执行记录

## 2026-08-03
- 首次执行。refresh_all.py 跑两轮，均成功 push。
- Steam 变更 2 项：异环 2026-04-23→2026-07-07（误判，已 override 恢复）、斗罗大陆：猎魂世界（海外版）TBA→2026-06-01（合理，保留）。
- 异环：Steam 页的 2026-07-07 只是 Steam/Epic 商店上架日，全平台公测为 2026-04-23，已按泰坦之旅2模式加入 overrides.json 并恢复旧值。override 总数 4→5。
- 新闻新增 146 条（重跑后增量 144 条）。
- commit：d7eefc7（首轮）→ 393de1b（override 修正后）。
- 经验：改 games.json 须保持 indent=2 + ensure_ascii=False 格式，否则整文件 diff；用 git show HEAD~1 找回旧字段。
