#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 references/ai-flavor-checklist.md 的检索表跑成一条命令。

用法：
    python3 checklist_scan.py <稿件.md>                 # 汇总（缺省按国际法基准）
    python3 checklist_scan.py <稿件.md> --field civil   # 民法稿用民法基准
    python3 checklist_scan.py <稿件.md> --context       # 带上下文，供逐处判断

为什么要脚本化：清单里的检索词表得手动 Ctrl+F 十几轮，实践中一定会漏。
而 grep 处理中文字符类会爆复杂度上限（ugrep 实测 `[^“”]{2,8}` 直接报错），
所以用 Python。

阈值来源（2026-09 用本脚本的同一批正则重测，MinerU 解析、mineru_body 抽正文）：
  intl  = 中国政法大学国际法学院 343 篇（缺省）
  civil = 中国政法大学民商经济法学院民法所 365 篇（2026-09-23 删去重复文件与立法建议稿后重算）
两套差别不小：民法的「是否+V」「而是」「破折号」「段末否定」都明显多，中英对照明显少。
**先定稿件属于哪个领域，再跑。** 拿国际法阈值查民法稿，会把正常写法报成免责腔。
密度类一律按**每万字**计，并注明该现象在语料中的出现率（国际法／民法）——
出现率低于 10% 的形式（如「谁能」），命中即改，不必看阈值。

**阈值都是提示，不是判决。** 每一条命中都要回到清单的判据问一句：
删掉它，受损的是论证还是只有气势？只伤气势的删，伤论证的留。
"""
import re, sys, os

NEG_BEFORE = re.compile(r'(不|无|非|未|难以|并|没有|勿|毋)[^。；]{0,12}$')
NEG_AFTER  = re.compile(r'^[^。；]{0,16}(不|无法|难以|并非|未|没有)')
NEG_TAIL   = re.compile(r'(不能|不足以|不当然|不宜|并非|不应|不会|不必|无法|不得|未必|不再|并不|难以)')

def load(path):
    s = open(path, encoding='utf-8').read()
    for h in ('## 注释', '## 脚注', '## 参考文献', '## 参考资料', '# 注释', '# 脚注'):
        s = s.split(h)[0]
    lines = [l for l in s.split('\n')
             if not l.lstrip().startswith(('#', '[^'))
             and not re.match(r'^\[\d+\]\s', l.lstrip())]
    body = '\n'.join(lines)
    paras = [re.sub(r'\[\^[^\]]+\]', '', l).strip() for l in lines]
    paras = [p for p in paras if len(p) >= 60 and not p.startswith(('>', '**', '|'))]
    return s, body, paras

# (名称, 模式, 方向, 每万字阈值, 语料出现率, 说明)
# 方向 'hi'=超过阈值报警  'lo'=低于阈值报警  'rare'=语料罕见，命中即报
# 阈值写成 {'intl': x, 'civil': y} 的，按 --field 取；写成单个数的，两个领域通用。
# 'hi' 的阈值取该领域语料的 Q3，除非说明里另有交代。
_Q = r'(?:谁|什么|怎么|怎样|如何|能否|是否|吗|呢|哪|为何|何以|[能该要可会行是有]不[能该要可会行是有])'
CHECKS = [
    # ── 口语问句代范畴：三个子类，命中即改
    # 2026-09 收紧：旧式只要一句里有两个短引号词就报，老师论文 78%（国际法）／81%（民法）
    # 都会命中，报出来的几乎全是术语引用（“损害”……“产品自损”）。
    # 现要求至少一个引号里是短问句，出现率降到 1%／6%，才配得上「命中即改」。
    ("口语问句·引号对举",
     r'[“](?=[^“”]{0,6}' + _Q + r')[^“”]{2,8}[”][^。]{0,24}[，、][^。]{0,24}[“][^“”]{2,8}[”]'
     r'|[“][^“”]{2,8}[”][^。]{0,24}[，、][^。]{0,24}[“](?=[^“”]{0,6}' + _Q + r')[^“”]{2,8}[”]',
     'rare', 0, "1%／6%", "★引号里的短问句成对出现，最扎眼的子类"),
    ("口语问句·谁能式", r'谁(能|可以|应|该|来|负责|有权)',
     'rare', 0, "3%／8%", "★「谁能调用」→「调用权限的归属」"),
    # 排除法而非通配 lookbehind：(?<![一-鿿]) 会把「回答能不能做」也挡掉（漏报），
    # 只需排掉真正造成误命中的「X能+不能」复合（功能不能、职能不能…）。
    ("口语问句·A不A",
     r'(?<!功)(?<!职)(?<!性)(?<!智)(?<!技)(?<!本)(?<!才)(?<!效)(?<!机)(?<!产)(?<!动)(?<!势)(?<!可)(?<!所)'
     r'(能不能|是不是|该不该|要不要|可不可以|行不行)',
     'rare', 0, "5%／12%", "★口语疑问格式→「是否具备…」（民法 12% 用过，逐处看是否口语）"),
    # ── 免责腔的词面标记（段落层指标见下方单独计算）
    ("是否+V 过密", r'是否[一-鿿]', 'hi', {'intl': 10.2, 'civil': 14.0}, "89%／96%",
     "中位 国际法 5.3／民法 8.6；陈述法定要件的留，可名词化的改"),
    ("本文自指", r'本文', 'hi', {'intl': 2.2, 'civil': 2.6}, "63%／76%",
     "中位 1.0／1.3；且 345 篇里只有 1.2% 提「本文的贡献」"),
    # ── 语域：这一项是**太少**才报警；民法 45% 的论文一处都没有，不设下限
    ("中英对照术语", r'（[A-Za-z][A-Za-z\s\.\-]{3,40}）|\([A-Za-z][A-Za-z\s\.\-]{3,40}\)',
     'lo', {'intl': 1.0, 'civil': 0}, "79%／55%", "中位 国际法 4.4／民法 0.9；外法术语首现处应配原文"),
    # ── 原有各项
    ("破折号 ——", r'——', 'hi', {'intl': 2.6, 'civil': 5.3}, "45%／70%",
     "Q3 国际法 1.9／民法 5.3；按语义改成冒号、「即」或另起一句"),
    # ⚠ 必须排除「因而是／反而是／然而是／继而是／转而是」——那是连词+系动词，不是负向排比。
    # 2026-09 实测：民法语料里这类只占 1.3%（25 : 1912），阈值几乎不受影响；
    # 但单篇稿子可以高得多——一份待改稿 9 处命中里 5 处是「因而是」，虚高 56%，
    # 直接把一个达标项报成超标。子串口径在单篇上的误差远大于在语料上的误差。
    ("负向排比 而是", r'(?<![因反然继转])而是', 'hi', {'intl': 3.2, 'civil': 4.8}, "72%／91%",
     "Q3 国际法 2.6／民法 4.8；留对照即论点的"),
    ("错语域词", r'(场域|锚点|进路|对接点|闸门|阀门|漂移|下标|三部曲|谱系|抓手|赋能|闭环|颗粒度|张力)',
     'rare', 0, "单词≤6%", "工程/社科/翻译腔词库，检出即换"),
    ("空间隐喻·入口式", r'(规范|制度|分析|论证|解释|理论|讨论|研究|法律|适用|客体|救济|程序)入口',
     'rare', 0, "0%／0%", "★两套语料都是 0 次。→ 规范依据／规制路径"),
    ("空间隐喻·空档式", r'空档|真空地带|夹层',
     'rare', 0, "1%／1%", "→ 缺位／空白／缺失"),
    ("空间隐喻·进入式", r'进入(视野|范围|规则|讨论|议程|判断|考量|评价|射程|话语)|落入|归入',
     'hi', 0.5, "9%／27%", "→ 属于／适用／成为…的对象"),
    ("空间隐喻·其他", r'射程|前移|溢出|嵌入|切口|锚定|支点|坐标',
     'hi', 0.5, "14%／12%", "方位词写法律关系＝翻译腔；换关系词（依据/路径/渠道）"),
    # 2026-09 由 rare 改 hi：彰显、凸显、标志着各有 7–17% 的老师论文用过，单处不必改
    ("膨胀意义词", r'(标志着|彰显|凸显|里程碑|具有重要意义|不可或缺|奠定了基础|新篇章|扮演着)',
     'hi', {'intl': 1.9, 'civil': 1.0}, "54%／44%", "超过 Q3 再删或降格"),
    ("新闻腔", r'(骤然|悄然|悍然|强势|锋芒|图景|答卷|篇章|序幕|破局|加码|按下了|打响了|交出了)',
     'rare', 0, "单词≤5%", "动词比事实更用力"),
    ("强调词堆积", r'(恰恰|恰好|正是|无疑|显然|毋庸置疑)', 'hi', 10.0, "76%／91%",
     "中位 国际法 1.9／民法 4.6；每千字超过 1 个（=10/万字）才算堆积"),
    ("绝对化断言", r'(唯一|任何|一切|绝不|从来|全部|必然)', 'hi', 0, "91%／91%",
     "逐处找反例；落在否定结构里的自动剔除"),
    ("元话语标记", r'(先作概念限定|可以预先给出|诚实的处理|再作回收|下文交代)',
     'rare', 0, "0%／0%", "语料 0 次，检出即删"),
    # 2026-09 从「元话语标记」拆出：这两个语料并不是 0（国际法 33%、民法 24% 的论文用过；
    # 旧注的 25%／16% 只数了「值得注意的是」，漏了「需要指出的是」）
    ("提示语 值得注意/需要指出", r'值得注意的是|需要指出的是',
     'hi', {'intl': 0.9, 'civil': 0}, "33%／24%", "段中承上启下的留；段首当填充语的删"),
    # 2026-09 由 rare 改 hi：「有学者认为」民法 32% 的论文用过，要查的是后面有没有注
    ("空泛归因", r'(有学者认为|学界普遍|一般认为)',
     'hi', {'intl': 0.6, 'civil': 1.0}, "26%／43%", "逐处查有无脚注；无注的补文献或删"),
    # 2026-09 新增：分号把一句切成几个短分句，style_stats 按。；？切句，句长随之偏低，
    # 会被误读成「句子偏碎」。实测一稿 43.4/万字，两套语料都在 P98 以上。
    ("分号密度", r'；', 'hi', {'intl': 14.9, 'civil': 20.2}, "—",
     "中位 国际法 9.7／民法 13.4；句长偏短时先查这一项，再谈合并句子"),
]

# 段落层指标（免责腔的主要证据）—— (名称, {领域: (语料中位, Q3)}, 说明)
# 按本脚本自己的段落口径（≥60 字）重算，比 SKILL.md 表里 mineru_body 口径（≥25 字）的
# 10.5／15.7 高约半个百分点，比民法的 14.0／20.0 高约 2 个百分点；两个口径不要混用。
PARA_CHECKS = [("段末否定收尾", {'intl': (11.1, 16.2), 'civil': (15.8, 22.0)},
                "高于 Q3 即免责腔：论证完成后仍不让结论站着")]

FIELDS = {'intl': '国际法学院 343 篇', 'civil': '民法所 365 篇'}

def pick(v, field):
    return v[field] if isinstance(v, dict) else v

def main():
    argv, field, pos = sys.argv[1:], 'intl', []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == '--field' and i + 1 < len(argv):
            field = argv[i + 1]; i += 2; continue
        if a.startswith('--field='):
            field = a.split('=', 1)[1]
        elif not a.startswith('--'):
            pos.append(a)
        i += 1
    if not pos or field not in FIELDS:
        sys.exit(__doc__)
    path = pos[0]
    ctx = '--context' in argv
    full, body, paras = load(path)
    n_char = len(re.findall(r'[一-鿿]', body))
    per = lambda n: n / max(n_char, 1) * 10000
    print(f"{os.path.basename(path)}　正文 {n_char} 汉字　{len(paras)} 段　"
          f"基准：{FIELDS[field]}（--field {field}）\n")
    print(f"{'检查项':<18}{'命中':>5}{'/万字':>7}{'阈值':>7}{'语料出现率':>10}  {'':<3}说明")
    print("-" * 108)
    flagged, notes = [], []
    for name, pat, mode, thr, freq, note in CHECKS:
        thr = pick(thr, field)
        if name == "分号密度":
            # 只数正文段：关键词行、表格行本身就用分号分隔，会虚高（实测一稿 53.0 → 43.1）
            ptxt = '\n'.join(paras)
            hits = list(re.compile(pat).finditer(ptxt))
            d = len(hits) / max(len(re.findall(r'[一-鿿]', ptxt)), 1) * 10000
            bad = d > thr
            print(f"{name:<18}{len(hits):>5}{d:>7.1f}{('>'+str(thr)):>9}{freq:>10}  {'⚠' if bad else '✓':<3}{note}")
            if bad:
                flagged.append((name, None))   # 分号太多，不逐处列上下文
            continue
        hits = list(re.compile(pat).finditer(body))
        if name == "绝对化断言":
            kept = [m for m in hits
                    if not NEG_BEFORE.search(body[max(0, m.start()-14):m.start()])
                    and not NEG_AFTER.search(body[m.end():m.end()+20])]
            notes.append(f"  绝对化：{len(hits)} 处命中，{len(hits)-len(kept)} 处落在否定结构内"
                         f"（法学限定语，自动剔除），实际待查 {len(kept)} 处。")
            hits = kept
        n = len(hits); d = per(n)
        bad = (n > thr) if mode == 'rare' else (d > thr if mode == 'hi' else d < thr)
        mark = "⚠" if bad else "✓"
        thr_s = ("命中即改" if mode == 'rare' else
                 ("不设" if mode == 'lo' and not thr else
                  (f"<{thr}" if mode == 'lo' else f">{thr}")))
        print(f"{name:<18}{n:>5}{d:>7.1f}{thr_s:>9}{freq:>10}  {mark:<3}{note}")
        if bad:
            flagged.append((name, hits))
    # 段落层
    if paras:
        tail = sum(1 for p in paras
                   if (ss := [x for x in re.split(r'(?<=[。？！])', p) if len(x) > 5])
                   and NEG_TAIL.search(ss[-1]))
        for name, byfield, note in PARA_CHECKS:
            med, q3 = byfield[field]
            r = tail / len(paras) * 100
            mark = "⚠" if r > q3 else "✓"
            print(f"{name:<18}{tail:>5}{r:>6.1f}%{('>'+str(q3)+'%'):>9}{('中位'+str(med)+'%'):>9}  {mark:<3}{note}")
    print()
    for x in notes:
        print(x)
    if notes:
        print()
    if not flagged:
        print("词面各项全部通过。")
    if ctx:
        for name, hits in flagged:
            if hits is None:
                continue
            print(f"\n══ {name}（{len(hits)} 处）")
            seen = set()
            for m in hits:
                a, b = max(0, m.start() - 28), m.end() + 26
                line = body[a:b].replace('\n', '')
                if line in seen:
                    continue
                seen.add(line)
                print(f"   …{line}…")
    elif flagged:
        print("加 --context 看每一处的上下文。")

if __name__ == '__main__':
    main()
