# -*- coding: utf-8 -*-
"""情态与限定强度：checklist_scan 不测的那一维。

用法：
    python3 scripts/hedge_stats.py <语料目录> <我的稿.md>          # 对照表
    python3 scripts/hedge_stats.py <语料目录> <我的稿.md> --list   # 逐条列出，供四分类

背景：`checklist_scan.py` 的免责腔三标记（段末否定率、自指、强断言）测的是**位置**
（句子结尾）和**人称**，测不到句中的**情态强度**。一篇每段都以正面判断收尾、
自指也不多的稿子，仍可以通篇「仍须／尚未／不足以／并不等于」，读者照样觉得
"不敢把话说完"。这个脚本补的就是那一维。

判读见 SKILL.md 第四节。要点：
  · ③「对照否定·全口径」才是公平比较——语料表达"做不到"用「难以/无法/并非」，
    待改稿用「不足以/不能仅/并不等于」，只测后者会把语料算成 0。
  · 家族②高而③正常 = 语料在断言做不到，你在声明自己没证到。
  · 划界型论文的②天然高于语料，逐条四分类后【骨】【引】留下即可，不必清零。

口径：语料和稿件都只数正文（2026-09 修）。
  · 语料 .md 视为 MinerU 解析稿，用 mineru_body.body_paras() 抽正文，正文段不足 15 的篇不计入；
    .txt 视为 pdf_body.py 已按字号剔掉脚注的正文，整篇读。
  · 稿件截掉注释/脚注/参考文献区与「<!-- 以下」之后的脚注定义，去掉标题、[^n] 注释行、
    引用块与表格行（同 word_check.py --file）。
  此前两边都整篇读，参考文献与脚注的汉字摊薄分母，和 SKILL.md 第四节"全量语料参照值"
  （正文口径）对不上：民法 ③ 的 Q3 整篇读是 26.5，正文口径 27.8；一份带 88 条脚注的稿子
  ③ 整篇读 23.9，只读正文 26.3。
"""
import re, os, sys, glob, statistics as st
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mineru_body import body_paras, expand, in_tmp

FAM = {
 "① 延宕（仍须/尚待/有待/尚未）":      r'仍[须需待]|尚[须需待]|还[须需]|有待|尚未|仍未|留待|容后',
 "② 自我设限（不足以/不能仅/并不等于）": r'不足以|不能仅|并不[等表意]|不等于|不表示|不意味|未必|不当然',
 "③ 对照否定·全口径（＋难以/无法/并非）": r'不足以|不能仅|并不[等表意]|不等于|不表示|不意味|未必|不当然|难以|无法|并非|并未|不能',
 "④ 前置让步（须承认/须注意/诚然）":    r'须承认|须注意|应当承认|诚然|固然|不可否认|值得注意的是',
 "⑤ 自指（本文/本章/笔者）":          r'本文|本章|笔者',
 "⑥ 前指过渡（下文/下一章/接下来）":    r'下文|后文|下一部分|下一章|下一节|以下将|接下来|本文第[一二三四五六七八]|第[一二三四五六七八]部分将',
}
CJK = re.compile(r'[一-鿿]')

def zh(t): return len(CJK.findall(t))

def scan(t):
    z = max(zh(t), 1)
    return {k: len(re.findall(p, t)) / z * 10000 for k, p in FAM.items()}

def load(p):
    fs = [p]
    if os.path.isdir(p):
        fs = [f for f in sorted(glob.glob(os.path.join(p, '**', '*.txt'), recursive=True))
              if not in_tmp(f, p)] + expand([p])
    out = []
    for f in fs:
        if f.endswith('.md'):
            ps = body_paras(f)
            if len(ps) < 15:
                continue
            t = '\n'.join(ps)
        else:
            t = open(f, encoding='utf-8', errors='ignore').read()
        out.append((os.path.basename(f), t))
    return out

def draft(path):
    raw = open(path, encoding='utf-8').read().split('<!-- 以下')[0]
    for h in ('## 注释', '## 脚注', '## 参考文献'):
        raw = raw.split(h)[0]
    return '\n'.join(l for l in raw.split('\n')
                     if not l.lstrip().startswith(('#', '[^', '>', '|')))

def main():
    a = [x for x in sys.argv[1:] if not x.startswith('--')]
    if len(a) < 2:
        print(__doc__); sys.exit(1)
    corpus, mine = load(a[0]), draft(a[1])
    if not corpus:
        print(f"语料目录里没有可用的 .txt/.md（.md 须是正文段 ≥15 的 MinerU 解析稿）：{a[0]}"); sys.exit(1)
    rows = [scan(t) for _, t in corpus]
    md = scan(mine)

    if '--list' in sys.argv:
        paras = [p for p in mine.split('\n') if p.strip() and not p.startswith('#')]
        n = 0
        for k, p in FAM.items():
            hits = [(i, m) for i, q in enumerate(paras) for m in re.finditer(p, q)]
            if not hits: continue
            print(f"\n═══ {k}（{len(hits)} 处）")
            for i, m in hits:
                n += 1
                q = paras[i]
                s, e = max(0, m.start() - 40), min(len(q), m.end() + 40)
                print(f"  [{n:03d}] 段{i+1} …{q[s:m.start()]}【{m.group()}】{q[m.end():e]}…")
        print(f"\n共 {n} 处。逐条标【引】法条原文／【骨】本文命题／【免】怕说满，只改【免】。")
        return

    print(f"{'家族':36s} {'本稿':>6s} {'中位':>6s} {'Q1':>6s} {'Q3':>6s} {'语料最大':>7s}")
    print("-" * 74)
    for k in FAM:
        vs = sorted(r[k] for r in rows)
        q = st.quantiles(vs, n=4) if len(vs) > 1 else [vs[0]] * 3
        flag = "  ⚠超语料最大" if md[k] > max(vs) else ("  ⚠>Q3" if md[k] > q[2] else "  ✓")
        print(f"{k:36s} {md[k]:6.1f} {st.median(vs):6.1f} {q[0]:6.1f} {q[2]:6.1f} {max(vs):7.1f}{flag}")
    print(f"\n本稿 {zh(mine)} 汉字；语料 {len(corpus)} 篇 {sum(zh(t) for _, t in corpus)} 汉字")
    print("加 --list 逐条列出。判读见 SKILL.md 第四节。")

if __name__ == '__main__':
    main()
