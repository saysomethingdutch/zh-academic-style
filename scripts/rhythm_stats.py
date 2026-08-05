#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""段落节奏统计器。

用法：
    python3 rhythm_stats.py <范文目录>          # 建基准
    python3 rhythm_stats.py <我的稿.md>         # 测待改稿
    python3 rhythm_stats.py <我的稿.md> --shape # 逐段打印形状，看同构

测什么、为什么：

AI 中文最难自查的特征不在词汇也不在句子，而在**段落的形状全都一样**。
它把段落当成"一个论点 + 展开"的固定容器，于是每段都是一个自足的微型论证闭环
（起论 → 展开 → 收束），而一个自足闭环天然就是 3–5 句、150–250 字。
结果：段长和句数的**离散度**塌陷。

真实范文不是这样。它们的段落长度由**功能**决定：
一句话的段用来放一个承重判断，二十句的段用来铺一条完整的材料链。
所以范文的离散度天然更高。

关键指标是 **CV（变异系数 = 标准差/均值）**，不是均值。
均值只说明作者习惯写多长，CV 说明作者**是否让段落随功能变长变短**。
"""
import re, sys, os, glob, statistics as st

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from enum_stats import paras_pdf, paras_text          # 复用段落提取

NEG = re.compile(r'(不能|不足以|不当然|不宜|并非|不应|不会|不必|无法|不得|未必|不再|并不|难以)')

def split_sents(p):
    return [x for x in re.split(r'(?<=[。？！])', p) if len(x) > 3]

def analyse(ps):
    L  = [len(p) for p in ps]
    SC = [len(split_sents(p)) for p in ps]
    tail = 0
    for p in ps:
        ss = split_sents(p)
        if ss and NEG.search(ss[-1]):
            tail += 1
    n = len(ps)
    return {
        "段": n,
        "段长中位": round(st.median(L)),
        "段长CV": round(st.pstdev(L) / st.mean(L), 3),
        "段长范围": f"{min(L)}–{max(L)}",
        "句数中位": round(st.median(SC)),
        "句数CV": round(st.pstdev(SC) / st.mean(SC), 3),
        "句数范围": f"{min(SC)}–{max(SC)}",
        "单句段%": round(sum(1 for c in SC if c == 1) / n * 100, 1),
        "长段8句+%": round(sum(1 for c in SC if c >= 8) / n * 100, 1),
        "段末否定%": round(tail / n * 100, 1),
    }

K = ["段", "段长中位", "段长CV", "段长范围", "句数中位", "句数CV",
     "句数范围", "单句段%", "长段8句+%", "段末否定%"]

def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    shape = '--shape' in sys.argv
    if not args:
        sys.exit(__doc__)
    files = []
    for a in args:
        if os.path.isdir(a):
            for e in ('*.pdf', '*.md', '*.txt'):
                files += sorted(glob.glob(os.path.join(a, e)))
        else:
            files += sorted(glob.glob(a))
    rows = []
    for f in files:
        try:
            ps = paras_pdf(f) if f.lower().endswith('.pdf') else paras_text(f)
        except Exception as e:
            print(f"  [跳过] {os.path.basename(f)[:38]} — {e}", file=sys.stderr); continue
        if len(ps) < 15:
            continue
        r = analyse(ps); r["文件"] = os.path.basename(f)[:26]
        rows.append((r, ps))
    print(f"{'文件':<28}" + "".join(f"{k:>11}" for k in K))
    for r, _ in sorted(rows, key=lambda t: t[0]["段长CV"]):
        print(f"{r['文件']:<28}" + "".join(f"{str(r[k]):>11}" for k in K))
    if len(rows) > 1:
        print("-" * (28 + 11 * len(K)))
        for k in ["段长中位", "段长CV", "句数中位", "句数CV", "单句段%", "长段8句+%", "段末否定%"]:
            v = [r[k] for r, _ in rows]
            print(f"  {k:<12} 均值 {st.mean(v):>7.2f}   范围 {min(v):>6.2f} – {max(v):>6.2f}")
    if shape:
        for r, ps in rows:
            print(f"\n{'='*72}\n{r['文件']}  逐段形状（看相邻段是否同构）\n{'='*72}")
            for i, p in enumerate(ps, 1):
                ss = split_sents(p)
                mark = " ◀否定收束" if ss and NEG.search(ss[-1]) else ""
                print(f"\n段{i:>3}  {len(p)}字 {len(ss)}句{mark}")
                print(f"      首｜{ss[0].strip()[:46]}")
                if len(ss) > 1:
                    print(f"      末｜{ss[-1].strip()[:46]}")

if __name__ == '__main__':
    main()
