#!/usr/bin/env python3
"""批量更新游戏数据 - 添加22款新游戏 + 修正日期 + 更新MMO + 清理重复"""
import json, re, os
from datetime import date

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(BASE, 'docs')

def m_frac(year_str, month=None, day=None):
    """计算 _m_frac 值"""
    if year_str == "TBA":
        return None
    y = int(year_str)
    if month is None:
        return float(y - 2026) * 12 + 9.5  # 年内
    if day is None:
        return float(y - 2026) * 12 + (month - 1)  # 月份
    return float(y - 2026) * 12 + (month - 1) + (day - 1) / 30  # 精确到天

def excel_serial(d):
    """日期转Excel序列号"""
    return (d - date(1899, 12, 30)).days

# ========================
# 1. 读取 games.json
# ========================
with open(os.path.join(DOCS, 'data', 'games.json'), 'r', encoding='utf-8') as f:
    data = json.load(f)

print(f"更新前: A={len(data['a'])}, L={len(data['l'])}, M={len(data['m'])}")

# ========================
# 2. 清理重复条目
# ========================
# 重复1: 古墓丽影 (index 23 较简略, index 56 较详细) → 删除 index 23
# 重复2: Stranger Than Heaven (index 22 较简略, index 59 较详细但cn名用了英文) → 删除 index 22, 修正 index 59 的 cn
to_remove = []
a = data['a']
for i, g in enumerate(a):
    if g.get('en') == 'Tomb Raider: Legacy of Atlantis' and g.get('developer') == 'Crystal Dynamics' and '/' not in g.get('developer', ''):
        # 这是较早的简略版本
        to_remove.append(i)
    if g.get('en') == 'Stranger Than Heaven' and g.get('cn') == 'Stranger Than Heaven':
        # cn用了英文名，修正为中文
        g['cn'] = '异于天堂'
    if g.get('en') == 'Stranger Than Heaven' and g.get('developer') in ('RGG Studio', '如龙工作室'):
        # 较早的简略版本
        to_remove.append(i)

# 删除较早的重复条目（保留更详细的后续版本）
to_remove = sorted(set(to_remove), reverse=True)
print(f"删除重复条目: {to_remove}")
for idx in to_remove:
    print(f"  - 删除 #{idx+1}: {a[idx]['cn']} | {a[idx]['en']}")
    a.pop(idx)

# ========================
# 3. 更新已有游戏日期
# ========================
updates_a = {
    'Wo Long 2: Wings of Ember': {
        'date': '2027-03-04', 'date_raw': '2027-03-04', 'window': 'Q1',
        '_m_frac': m_frac('2027', 3, 4), '_precision': 'day',
        'desc': 'Team Ninja开发的三国题材诛死动作游戏续作。延续前作的化解战斗系统，新增更多武器类型与妖怪敌人，在黑暗三国世界观中挑战强敌与Boss。Alpha Demo于TGS 2026提供试玩（至9月30日），2027年3月4日正式发售。'
    },
    'Persona 4 Revival': {
        'date': '2027-02-18', 'date_raw': '2027-02-18', 'window': 'Q1',
        '_m_frac': m_frac('2027', 2, 18),
        'desc': 'Atlus开发的女神异闻录4重制版，Unreal Engine 5打造，全3D重制稻羽市场景，刷新战斗UI与迷宫机制，加入全语音脚本，保留社群模拟系统。2027年2月18日发售，登陆全平台含Switch 2。'
    },
}

for g in a:
    for en, upd in updates_a.items():
        if g.get('en') == en:
            print(f"更新 {g['cn']}: {g.get('date')} → {upd['date']}")
            g.update(upd)

# 更新MMO游戏
updates_m = {
    '永恒之塔2': {
        'date': '2026-10-05', 'date_raw': '2026-10-05', 'window': 'Q4',
        '_m_frac': m_frac('2026', 10, 5), '_precision': 'day',
        'desc': 'NCSoft开发的《永恒之塔》正统续作。延续前作的飞行战斗与天魔两族对抗核心，以UE5引擎打造次世代画面与无缝大世界，2026年10月5日率先推出全球版，国服代理与版号尚未确定。'
    },
    '伊莫': {
        'year': '2026', 'window': 'Q3', 'date_raw': '2026-09-16',
        'date': '2026-09-16', '_m_frac': m_frac('2026', 9, 16), '_precision': 'day',
        'desc': 'Pawprint Studio开发的奇幻生物养成MMORPG。以收集与培养萌系生物"伊莫"为核心玩法，融合开放世界探索、回合策略战斗与多人协作，画风可爱治愈，主打休闲向MMO体验。2026年9月16日上线。'
    },
}

for g in data['m']:
    for cn, upd in updates_m.items():
        if g.get('cn') == cn:
            print(f"更新MMO {g['cn']}: {g.get('date')} → {upd.get('date', g.get('date'))}")
            g.update(upd)

# ========================
# 4. 添加22款新游戏
# ========================
new_games = [
    # --- A类: 3A/高关注度 ---
    {
        'cn': '女神异闻录6', 'en': 'Persona 6', 'developer': 'ATLUS / SEGA',
        'year': 'TBA', 'window': 'TBA', 'date_raw': 'TBA', 'date': 'TBA',
        '_m_frac': None, '_precision': 'tba', 'type': 'Release', 'platform': '端游',
        'desc': 'ATLUS《女神异闻录》系列最新编号作品，十年来首部全新编号作。Xbox Games Showcase 2026.6.7官宣，设定在现代日本，全新独立故事与新角色阵容，无需系列前作经验。PS5/Xbox/PC同步首发，Day One加入Game Pass。发售日在Persona 4 Revival（2027.2.18）之后。'
    },
    {
        'cn': '密特罗德：贪婪', 'en': 'Metroid Ravenous', 'developer': 'Nintendo',
        'year': '2027', 'window': 'Q1', 'date_raw': '2027-01-28', 'date': '2027-01-28',
        '_m_frac': m_frac('2027', 1, 28), '_precision': 'day', 'type': 'Release', 'platform': '端游',
        'desc': 'Nintendo的《密特罗德》系列2D动作冒险新作，Switch 2独占。Samus Aran在全新2D横版冒险中面对更致命的敌人，融合系列经典探索与Switch 2硬件性能。2027年1月28日发售，Nintendo Direct 9/9公布。'
    },
    {
        'cn': '血污：猩红缔约', 'en': 'Bloodstained: The Scarlet Engagement', 'developer': 'ArtPlay (五十岚孝司)',
        'year': '2027', 'window': '年内 Within the Year', 'date_raw': '2027', 'date': '2027 年内',
        '_m_frac': m_frac('2027'), '_precision': 'window', 'type': 'Release', 'platform': '端游',
        'desc': '五十岚孝司（IGA）领衔ArtPlay开发的《血污》系列新作，Ritual of the Night的前传。双主角Leonard Brandon与Alexander Kyteler并肩作战，2.5D哥特风格设定在16世纪英格兰。原定2026年发售，2026年8月宣布延期至2027年进行最终打磨。PS5/Xbox/PC。'
    },
    {
        'cn': '电锯甜心2 Back2Back', 'en': 'Lollipop Chainsaw 2 Back2Back', 'developer': 'JP Universe (田畑端)',
        'year': '2027', 'window': '年内 Within the Year', 'date_raw': '2027', 'date': '2027 年内',
        '_m_frac': m_frac('2027'), '_precision': 'window', 'type': 'Release', 'platform': '端游',
        'desc': 'Dragami Games与Koei Tecmo联合推出，由《最终幻想15》总监田畑端执导的《电锯甜心》正统续作。Juliet Starling回归，在重建的电影工业都市Jaredwood中对抗全新丧尸潮。原作编剧Masahiro Yuki回归，但无Suda51与James Gunn参与。PS5平台，2027年发售。TGS 2026公布。'
    },
    {
        'cn': '绯红沙漠', 'en': 'Crimson Desert', 'developer': 'Pearl Abyss',
        'year': '2026', 'window': 'Q1', 'date_raw': '2026-03-20', 'date': '2026-03-20',
        '_m_frac': m_frac('2026', 3, 20), '_precision': 'day', 'type': 'Release', 'platform': '端游',
        'desc': 'Pearl Abyss（《黑色沙漠》开发商）开发的开放世界动作冒险RPG，自研BlackSpace引擎打造。主角Kliff带领"灰色鬃毛"佣兵团在Pywel大陆冒险，融合剑盾/枪/斧等多种武器组合战斗、骑乘/滑翔/攀岩等移动方式。2026年3月20日全球发售，首周销量300万。DLC"Charting the Unknown"于2026年10月15日推出。'
    },
    {
        'cn': '最终幻想 共鸣', 'en': 'Final Fantasy Resonance', 'developer': 'Square Enix',
        'year': '2026', 'window': 'Q4', 'date_raw': '2026-10-22', 'date': '2026-10-22',
        '_m_frac': m_frac('2026', 10, 22), '_precision': 'day', 'type': 'Release', 'platform': '端游',
        'desc': 'Square Enix开发的HD-2D风格回合制RPG，基于手游《Brave Exvius》世界观，含Sephiroth等标志性角色。State of Play 9/3公布，Demo已于9月3日上线PS5，存档可继承至正式版。2026年10月22日发售。'
    },
    {
        'cn': '普拉格玛塔', 'en': 'Pragmata', 'developer': 'Capcom',
        'year': 'TBA', 'window': 'TBA', 'date_raw': 'TBA', 'date': 'TBA',
        '_m_frac': None, '_precision': 'tba', 'type': 'Release', 'platform': '端游',
        'desc': 'Capcom开发的科幻动作冒险游戏，2020年首次公布后多次延期。设定在月球基地，玩家扮演太空服宇航员与神秘AI少女合作探索。TGS 2026展出席位，具体发售日待定。PS5/Xbox/PC。'
    },
    {
        'cn': '火焰纹章：命运之织', 'en': "Fire Emblem: Fortune's Weave", 'developer': 'Nintendo (Intelligent Systems)',
        'year': '2026', 'window': 'Q3', 'date_raw': '2026-09-17', 'date': '2026-09-17',
        '_m_frac': m_frac('2026', 9, 17), '_precision': 'day', 'type': 'Release', 'platform': '端游',
        'desc': 'Nintendo《火焰纹章》系列策略RPG新作，Switch 2平台。设定在Dagdan帝国，角色参与Heroic Games竞技，融合策略战斗与角色羁绊系统。Nintendo Direct 9/9公布。'
    },
    {
        'cn': '数码宝贝物语：时空旅人', 'en': 'Digimon Story: Time Stranger', 'developer': 'Bandai Namco',
        'year': 'TBA', 'window': 'TBA', 'date_raw': 'TBA', 'date': 'TBA',
        '_m_frac': None, '_precision': 'tba', 'type': 'Release', 'platform': '端游',
        'desc': 'Bandai Namco《数码宝贝物语》系列RPG新作。State of Play 9/3展出，跨越时空的数码宝贝冒险。具体发售日与平台待定。'
    },
    {
        'cn': '勇者斗恶龙7 重制版', 'en': 'Dragon Quest VII Remake', 'developer': 'Square Enix',
        'year': 'TBA', 'window': 'TBA', 'date_raw': 'TBA', 'date': 'TBA',
        '_m_frac': None, '_precision': 'tba', 'type': 'Release', 'platform': '端游',
        'desc': 'Square Enix《勇者斗恶龙7》重制版。TGS 2026与Nintendo Direct 9/9公布，现代技术重塑经典JRPG。具体发售日与平台待定。'
    },
    # --- B类: 中关注度 ---
    {
        'cn': '衰灭之回响', 'en': 'Fading Echo', 'developer': 'Nintendo',
        'year': '2026', 'window': 'Q3', 'date_raw': '2026-09-17', 'date': '2026-09-17',
        '_m_frac': m_frac('2026', 9, 17), '_precision': 'day', 'type': 'Release', 'platform': '端游',
        'desc': 'Nintendo的动作RPG冒险新作，Switch 2平台。主角"One"可使用Æther之力，在人类形态与水生生物形态间切换，探索多元宇宙、解谜与战斗。Nintendo Direct 9/9公布，含Demo。'
    },
    {
        'cn': '猩红狂想曲', 'en': 'Rhapsody in Scarlet', 'developer': 'Konami',
        'year': 'TBA', 'window': 'TBA', 'date_raw': 'TBA', 'date': 'TBA',
        '_m_frac': None, '_precision': 'tba', 'type': 'Release', 'platform': '端游',
        'desc': 'Konami开发的新作动作冒险游戏。设定在1920年代纽约，爵士女巫Ellie Meyers使用魔法与魔兽在摩天大楼间施展爽快连招。State of Play 9/3公布，PS5平台。'
    },
    {
        'cn': '蕾芙 NoiR', 'en': 'Rev: NoiR', 'developer': 'Konami',
        'year': '2027', 'window': '年内 Within the Year', 'date_raw': '2027', 'date': '2027 年内',
        '_m_frac': m_frac('2027'), '_precision': 'window', 'type': 'Release', 'platform': '端游',
        'desc': 'Konami开发的RPG新作。主角Asch与Finé踏上阻止"Luminescence"灾祸的旅程，这场灾祸会杀死一切被触及的生命。State of Play 9/3公布，PS5平台，2027年发售。'
    },
    {
        'cn': '赫奇亚库塔：突围', 'en': 'Gachiakuta: Breakout', 'developer': 'Com2uS',
        'year': '2027', 'window': '年内 Within the Year', 'date_raw': '2027', 'date': '2027 年内',
        '_m_frac': m_frac('2027'), '_precision': 'window', 'type': 'Release', 'platform': '端游',
        'desc': 'Com2uS开发的生存动作RPG，基于同名TV动画《Gachiakuta》。主角Rudo Surebrec在卡通风格世界中展开以近战为主的动作战斗。Xbox TGS Showcase公布，Xbox/PS5/Steam平台，2027年发售。'
    },
    {
        'cn': '炼金工房 卡莉亚', 'en': 'Atelier Karia: The Night Kingdom & the Guide of Memories', 'developer': 'Koei Tecmo (Gust)',
        'year': 'TBA', 'window': 'TBA', 'date_raw': 'TBA', 'date': 'TBA',
        '_m_frac': None, '_precision': 'tba', 'type': 'Release', 'platform': '端游',
        'desc': 'Gust开发《炼金工房》系列最新主线作品。Xbox TGS Showcase展出，展示新战斗画面与回归角色Yumia，融合炼金合成与夜之王国探索。发售日待定。'
    },
    {
        'cn': '德卡波利斯', 'en': 'DECAPOLICE', 'developer': 'LEVEL-5',
        'year': 'TBA', 'window': 'TBA', 'date_raw': 'TBA', 'date': 'TBA',
        '_m_frac': None, '_precision': 'tba', 'type': 'Release', 'platform': '端游',
        'desc': 'LEVEL-5开发的动作冒险新作。TGS 2026展出，来自《雷顿教授》《妖怪手表》团队的新IP。发售日与平台待定。'
    },
    {
        'cn': '妖怪手表2：幽灵领域', 'en': "Yo-kai Watch 2: Haunted Domain", 'developer': 'LEVEL-5',
        'year': 'TBA', 'window': 'TBA', 'date_raw': 'TBA', 'date': 'TBA',
        '_m_frac': None, '_precision': 'tba', 'type': 'Release', 'platform': '端游',
        'desc': 'LEVEL-5《妖怪手表》系列新作RPG。TGS 2026与Nintendo Direct 9/9公布，发售日与平台待定。'
    },
    {
        'cn': '星祈', 'en': 'Astrae Oratio', 'developer': 'Dynamis One / NCSoft',
        'year': '2027', 'window': '年内 Within the Year', 'date_raw': '2027', 'date': '2027 年内',
        '_m_frac': m_frac('2027'), '_precision': 'window', 'type': 'Release', 'platform': '端游',
        'desc': 'NCSoft发行、Dynamis One开发的RPG。设定在现实与魔法共存的世界，玩家扮演特别区事务所公务员调查魔法相关事件。TGS 2026韩国厂商展出，2027年发售。'
    },
    {
        'cn': '食人鲨2', 'en': 'Maneater 2', 'developer': 'Tripwire Interactive',
        'year': '2027', 'window': '年内 Within the Year', 'date_raw': '2027', 'date': '2027 年内',
        '_m_frac': m_frac('2027'), '_precision': 'window', 'type': 'Release', 'platform': '端游',
        'desc': 'Tripwire Interactive开发的鲨鱼动作RPG续作。玩家操控公牛鲨在Neptune\'s Kingdom豪华岛屿主题公园中进食、探索、进化。UE5引擎打造，State of Play 9/3公布，2027年发售。'
    },
    {
        'cn': '记忆边缘', 'en': 'Edge of Memories', 'developer': 'TBA',
        'year': 'TBA', 'window': 'TBA', 'date_raw': 'TBA', 'date': 'TBA',
        '_m_frac': None, '_precision': 'tba', 'type': 'Release', 'platform': '端游',
        'desc': 'RPG新作，以"Soul Whisperer"能力为核心，展示多种环境场景。Xbox TGS Showcase发布新预告片，发售日待定。'
    },
    {
        'cn': '咒术回战 RUMBLE', 'en': 'Jujutsu Kaisen RUMBLE: SURVIVATON', 'developer': 'Shueisha Games / poncle',
        'year': 'TBA', 'window': 'TBA', 'date_raw': 'TBA', 'date': 'TBA',
        '_m_frac': None, '_precision': 'tba', 'type': 'Release', 'platform': '端游',
        'desc': '集英社游戏与《吸血鬼幸存者》制作人poncle联合开发的8人格斗/动作游戏，基于《咒术回战》IP。TGS 2026公布，发售日待定。'
    },
    # --- C类: 边界情况 ---
    {
        'cn': '死亡勇者', 'en': 'Valor Mortis', 'developer': 'One More Level',
        'year': '2026', 'window': 'Q3', 'date_raw': '2026-09-24', 'date': '2026-09-24',
        '_m_frac': m_frac('2026', 9, 24), '_precision': 'day', 'type': 'Release', 'platform': '端游',
        'desc': 'One More Level（幽影行者团队）开发的第一人称动作魂Like新作。设定在超自然色彩的19世纪拿破仑战争时期，玩家扮演从死亡中苏醒的士兵William，融合枪炮与超自然神圣力量对抗怪物。拿破仑由文森·卡索配音。2026年9月24日发售，首日加入Game Pass。Xbox/PS5/PC。'
    },
]

print(f"\n添加 {len(new_games)} 款新游戏:")
for g in new_games:
    print(f"  + {g['cn']} | {g['en']} | {g['date']}")
    a.append(g)

# 按日期排序（保持现有顺序，新游戏追加到末尾）
# 实际上不排序，保持手动顺序

print(f"\n更新后: A={len(data['a'])}, L={len(data['l'])}, M={len(data['m'])}")
print(f"总计: {len(data['a']) + len(data['l']) + len(data['m'])}")

# ========================
# 5. 写入 games.json
# ========================
games_json_path = os.path.join(DOCS, 'data', 'games.json')
with open(games_json_path, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
print(f"\n✅ 已写入 {games_json_path}")

# ========================
# 6. 写入 games.min.json
# ========================
games_min_path = os.path.join(DOCS, 'data', 'games.min.json')
with open(games_min_path, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, separators=(',', ':'))
print(f"✅ 已写入 {games_min_path}")

# ========================
# 7. 写入 games_inline.js
# ========================
games_inline_path = os.path.join(DOCS, 'data', 'games_inline.js')
games_js_str = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
with open(games_inline_path, 'w', encoding='utf-8') as f:
    f.write('// 游戏数据 · 自动生成（scripts/build_inline.py）\n')
    f.write('const GAMES = ')
    f.write(games_js_str)
    f.write(';\n')
print(f"✅ 已写入 {games_inline_path}")

# ========================
# 8. 更新 index.html 内联数据
# ========================
index_path = os.path.join(DOCS, 'index.html')
with open(index_path, 'r', encoding='utf-8') as f:
    html = f.read()

# 替换 const GAMES = {...};
# 使用正则匹配整行
pattern = r'const GAMES\s*=\s*\{.*?\};'
replacement = 'const GAMES = ' + games_js_str + ';'
new_html = re.sub(pattern, replacement, html, count=1, flags=re.DOTALL)

if new_html != html:
    with open(index_path, 'w', encoding='utf-8') as f:
        f.write(new_html)
    print(f"✅ 已更新 {index_path} (内联GAMES)")
else:
    print(f"⚠️  index.html 未找到 GAMES 数据，跳过")

# ========================
# 9. 更新 schedule.json
# ========================
schedule_path = os.path.join(DOCS, 'data', 'schedule.json')
with open(schedule_path, 'r', encoding='utf-8') as f:
    schedule = json.load(f)

# 添加新游戏到 sheet1 (动作游戏)
for game in new_games:
    # 计算 Excel 序列号
    if game['_precision'] == 'day':
        parts = game['date'].split('-')
        d = date(int(parts[0]), int(parts[1]), int(parts[2]))
        date_serial = str(excel_serial(d))
        date_iso = game['date']
    else:
        date_serial = game.get('date_raw', '')
        date_iso = ''

    # 确定window字段值
    window = game.get('window', 'TBA')

    entry = {
        "发售年份\nRelease Year": game.get('year', 'TBA'),
        "档期\nRelease Window": window,
        "具体发售时间\nRelease Date": date_serial,
        "游戏中文名\nChinese Name": game['cn'],
        "游戏英文名\nEnglish Name": game['en'],
        "开发商\nDeveloper": game['developer'],
        "_row": len(schedule['sheet1']) + 2,
        "_date_iso": date_iso,
        "简介\nDescription": game['desc'],
        "platform": game.get('platform', '端游'),
        "type": game.get('type', 'Release'),
    }
    schedule['sheet1'].append(entry)

# 更新已修改的游戏在 schedule.json 中
# 需要更新 Wo Long 2 和 Persona 4 Revival 在 sheet1 中的记录
for entry in schedule['sheet1']:
    # 更新 Wo Long 2
    if entry.get('游戏英文名\nEnglish Name') == 'Wo Long 2: Wings of Ember':
        d = date(2027, 3, 4)
        entry['具体发售时间\nRelease Date'] = str(excel_serial(d))
        entry['_date_iso'] = '2027-03-04'
        entry['档期\nRelease Window'] = 'Q1'
        entry['简介\nDescription'] = new_games[0]['desc'] if False else 'Team Ninja开发的三国题材诛死动作游戏续作。延续前作的化解战斗系统，新增更多武器类型与妖怪敌人，在黑暗三国世界观中挑战强敌与Boss。Alpha Demo于TGS 2026提供试玩（至9月30日），2027年3月4日正式发售。'

    # 更新 Persona 4 Revival
    if entry.get('游戏英文名\nEnglish Name') == 'Persona 4 Revival':
        d = date(2027, 2, 18)
        entry['具体发售时间\nRelease Date'] = str(excel_serial(d))
        entry['_date_iso'] = '2027-02-18'
        entry['档期\nRelease Window'] = 'Q1'
        entry['简介\nDescription'] = 'Atlus开发的女神异闻录4重制版，Unreal Engine 5打造，全3D重制稻羽市场景，刷新战斗UI与迷宫机制，加入全语音脚本，保留社群模拟系统。2027年2月18日发售，登陆全平台含Switch 2。'

# 删除 schedule.json 中的重复条目
# 找到重复的 Tomb Raider 和 Stranger Than Heaven
entries_to_remove = []
for i, entry in enumerate(schedule['sheet1']):
    en = entry.get('游戏英文名\nEnglish Name', '')
    dev = entry.get('开发商\nDeveloper', '')
    # 标记较早的简略版本
    if en == 'Tomb Raider: Legacy of Atlantis' and dev == 'Crystal Dynamics' and '/' not in dev:
        entries_to_remove.append(i)
    if en == 'Stranger Than Heaven' and dev in ('RGG Studio', '如龙工作室'):
        entries_to_remove.append(i)

entries_to_remove = sorted(set(entries_to_remove), reverse=True)
print(f"\nschedule.json 删除重复: {entries_to_remove}")
for idx in entries_to_remove:
    e = schedule['sheet1'][idx]
    print(f"  - 删除: {e.get('游戏中文名\\nChinese Name', '')} | {e.get('游戏英文名\\nEnglish Name', '')}")
    schedule['sheet1'].pop(idx)

# 更新 MMO 条目在 schedule.json 中
if 'sheet3' in schedule:
    for entry in schedule['sheet3']:
        cn = entry.get('游戏中文名\nChinese Name', '')
        if cn == '永恒之塔2':
            d = date(2026, 10, 5)
            entry['具体发售时间\nRelease Date'] = str(excel_serial(d))
            entry['_date_iso'] = '2026-10-05'
            entry['档期\nRelease Window'] = 'Q4'
            entry['简介\nDescription'] = 'NCSoft开发的《永恒之塔》正统续作。延续前作的飞行战斗与天魔两族对抗核心，以UE5引擎打造次世代画面与无缝大世界，2026年10月5日率先推出全球版，国服代理与版号尚未确定。'
        if cn == '伊莫':
            d = date(2026, 9, 16)
            entry['具体发售时间\nRelease Date'] = str(excel_serial(d))
            entry['_date_iso'] = '2026-09-16'
            entry['发售年份\nRelease Year'] = '2026'
            entry['档期\nRelease Window'] = 'Q3'
            entry['简介\nDescription'] = 'Pawprint Studio开发的奇幻生物养成MMORPG。以收集与培养萌系生物"伊莫"为核心玩法，融合开放世界探索、回合策略战斗与多人协作，画风可爱治愈，主打休闲向MMO体验。2026年9月16日上线。'

with open(schedule_path, 'w', encoding='utf-8') as f:
    json.dump(schedule, f, ensure_ascii=False, indent=2)
print(f"\n✅ 已更新 {schedule_path}")

# ========================
# 验证
# ========================
print("\n=== 验证 ===")
with open(os.path.join(DOCS, 'data', 'games.json'), 'r', encoding='utf-8') as f:
    v = json.load(f)
print(f"games.json: A={len(v['a'])}, L={len(v['l'])}, M={len(v['m'])}, 总计={len(v['a'])+len(v['l'])+len(v['m'])}")

# 验证新游戏存在
new_cns = [g['cn'] for g in new_games]
found = [g['cn'] for g in v['a'] if g['cn'] in new_cns]
print(f"新游戏验证: {len(found)}/{len(new_cns)} 已找到")

# 验证日期更新
for g in v['a']:
    if g['en'] == 'Wo Long 2: Wings of Ember':
        print(f"卧龙2 日期: {g['date']}")
    if g['en'] == 'Persona 4 Revival':
        print(f"P4R 日期: {g['date']}")
for g in v['m']:
    if g['cn'] == '永恒之塔2':
        print(f"永恒之塔2 日期: {g['date']}")
    if g['cn'] == '伊莫':
        print(f"伊莫 日期: {g['date']}")

# 验证重复已清理
en_counts = {}
for g in v['a']:
    en = g['en']
    en_counts[en] = en_counts.get(en, 0) + 1
dups = {k: v for k, v in en_counts.items() if v > 1}
if dups:
    print(f"⚠️ 仍有重复: {dups}")
else:
    print("✅ 无重复条目")

print("\n✅ 全部更新完成!")
