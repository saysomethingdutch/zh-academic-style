#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 references/ai-flavor-checklist.md 的检索表跑成一条命令。

用法：
    python3 checklist_scan.py <稿件.md>            # 汇总
    python3 checklist_scan.py <稿件.md> --context  # 带上下文，供逐处判断

为什么要脚本化：清单里的检索词表得手动 Ctrl+F 十几轮，实践中一定会漏。
而 grep 处理中文字符类会爆复杂度上限（ugrep 实测 `[^“”]{2,8}` 直接报错），
所以用 Python。

阈值来源：中国政法大学国际法学院 346 篇期刊论文（MinerU 解析，2026-08）。
密度类一律按**每万字**计，并注明该现象在 346 篇中的出现率——
出现率低于 10% 的形式（如「谁能」「能不能」），命中即改，不必看阈值。

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
CHECKS = [
    # ── 口语问句代范畴：三个子类，语料出现率都低于 6%，命中即改
    ("口语问句·引号对举", r'[“][^“”]{2,8}[”][^。]{0,24}[，、][^。]{0,24}[“][^“”]{2,8}[”]',
     'rare', 0, "2%", "★引号＋短问句＋对仗，最扎眼的子类"),
    ("口语问句·谁能式", r'谁(能|可以|应|该|来|负责|有权)',
     'rare', 0, "3%", "★「谁能调用」→「调用权限的归属」"),
    # 排除法而非通配 lookbehind：(?<![一-鿿]) 会把「回答能不能做」也挡掉（漏报），
    # 只需排掉真正造成误命中的「X能+不能」复合（功能不能、职能不能…）。
    ("口语问句·A不A",
     r'(?<!功)(?<!职)(?<!性)(?<!智)(?<!技)(?<!本)(?<!才)(?<!效)(?<!机)(?<!产)(?<!动)(?<!势)(?<!可)(?<!所)'
     r'(能不能|是不是|该不该|要不要|可不可以|行不行)',
     'rare', 0, "5%", "★口语疑问格式→「是否具备…」"),
    # ── 免责腔的词面标记（段落层指标见下方单独计算）
    ("是否+V 过密", r'是否[一-鿿]', 'hi', 10.2, "89%",
     "语料中位 5.3／Q3 10.2；陈述法定要件的留，可名词化的改"),
    ("本文自指", r'本文', 'hi', 2.2, "—",
     "语料中位 1.0／Q3 2.2；且 345 篇里只有 1.2% 提「本文的贡献」"),
    # ── 语域：这一项是**太少**才报警
    ("中英对照术语", r'（[A-Za-z][A-Za-z\s\.\-]{3,40}）|\([A-Za-z][A-Za-z\s\.\-]{3,40}\)',
     'lo', 1.0, "—", "语料中位 4.4／Q1 1.0；外法术语首现处应配原文"),
    # ── 原有各项
    ("破折号 ——", r'——', 'hi', 2.6, "—", "语料每段 0.00–0.05；正文超过 5 处必处理"),
    ("负向排比 而是", r'而是', 'hi', 3.2, "—", "2.5 万字超过 8 处就要砍；留对照即论点的"),
    ("错语域词", r'(场域|锚点|进路|对接点|闸门|阀门|漂移|下标|三部曲|谱系|抓手|赋能|闭环|颗粒度|张力)',
     'rare', 0, "—", "工程/社科/翻译腔词库，检出即换"),
    ("空间隐喻·入口式", r'(规范|制度|分析|论证|解释|理论|讨论|研究|法律|适用|客体|救济|程序)入口',
     'rare', 0, "0%", "★345 篇里 0 次。→ 规范依据／规制路径"),
    ("空间隐喻·空档式", r'空档|真空地带|夹层',
     'rare', 0, "0%", "★345 篇里 0 次。→ 缺位／空白／缺失"),
    ("空间隐喻·进入式", r'进入(视野|范围|规则|讨论|议程|判断|考量|评价|射程|话语)|落入|归入',
     'hi', 0.5, "5%", "语料 0.09/万字。→ 属于／适用／成为…的对象"),
    ("空间隐喻·其他", r'射程|前移|溢出|嵌入|切口|锚定|支点|坐标',
     'hi', 0.5, "1–6%", "方位词写法律关系＝翻译腔；换关系词（依据/路径/渠道）"),
    ("膨胀意义词", r'(标志着|彰显|凸显|里程碑|具有重要意义|不可或缺|奠定了基础|新篇章|扮演着)',
     'rare', 0, "—", "删或降格"),
    ("新闻腔", r'(骤然|悄然|悍然|强势|锋芒|图景|答卷|篇章|序幕|破局|加码|按下了|打响了|交出了)',
     'rare', 0, "—", "动词比事实更用力"),
    ("强调词堆积", r'(恰恰|恰好|正是|无疑|显然|毋庸置疑)', 'hi', 10.0, "—",
     "语料中位 2.6／万字；每千字超过 1 个（=10/万字）才算堆积"),
    ("绝对化断言", r'(唯一|任何|一切|绝不|从来|全部|必然)', 'hi', 0, "—",
     "逐处找反例；落在否定结构里的自动剔除"),
    ("元话语标记", r'(先作概念限定|可以预先给出|诚实的处理|再作回收|下文交代|值得注意的是|需要指出的是)',
     'rare', 0, "0%", "语料全部为 0，检出即删"),
    ("空泛归因", r'(有学者认为|学界普遍|一般认为)', 'rare', 0, "—", "无脚注的一律补文献或删"),
]

# 段落层指标（免责腔的主要证据）—— (名称, 语料中位, Q3, 说明)
PARA_CHECKS = [("段末否定收尾", 10.5, 15.7, "高于 Q3 即免责腔：论证完成后仍不让结论站着")]

def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    path = sys.argv[1]
    ctx = '--context' in sys.argv
    full, body, paras = load(path)
    n_char = len(re.findall(r'[一-鿿]', body))
    per = lambda n: n / max(n_char, 1) * 10000
    print(f"{os.path.basename(path)}　正文 {n_char} 汉字　{len(paras)} 段\n")
    print(f"{'检查项':<18}{'命中':>5}{'/万字':>7}{'阈值':>7}{'语料':>6}  {'':<3}说明")
    print("-" * 104)
    flagged, notes = [], []
    for name, pat, mode, thr, freq, note in CHECKS:
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
                 (f"<{thr}" if mode == 'lo' else f">{thr}"))
        print(f"{name:<18}{n:>5}{d:>7.1f}{thr_s:>9}{freq:>6}  {mark:<3}{note}")
        if bad:
            flagged.append((name, hits))
    # 段落层
    if paras:
        tail = sum(1 for p in paras
                   if (ss := [x for x in re.split(r'(?<=[。？！])', p) if len(x) > 5])
                   and NEG_TAIL.search(ss[-1]))
        for name, med, q3, note in PARA_CHECKS:
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
