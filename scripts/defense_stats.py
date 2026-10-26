#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""defense_stats.py — the four signals that survive a surface-level de-AI pass (SKILL.md 五之四).

  防御性否定/万字   不构成|不等于|不能据此|只说明…不…  — limiting clauses with no claim to limit
  段末否定%         paragraph ends on a negative
  裸主题句段%       paragraph opens with a ≤22-char comma-free judgement used as a heading
  疑问并列          "谁负责什么、谁审核什么" question lists
  句首两字分布      --openers: which two characters start sentences (shows a monotone bridging tic)

Usage:
  defense_stats.py FILE [FILE...]            per-file table
  defense_stats.py --corpus DIR FILE          compare FILE against the Q1/median/Q3 of DIR/*.md
  defense_stats.py --openers FILE             top sentence openers
  defense_stats.py --list FILE                list every defensive sentence / bare topic sentence
Standard library only. Markdown input: footnote definitions ([^n]: …) and HTML comments are stripped.
"""
import glob
import re
import statistics as st
import sys
from collections import Counter

DEF = r"不构成|不等于|不能据此|不能直接|不能仅|不能简单|不足以|仅说明|只说明|不作为|并非|不意味着|不应据此|不能替代|不能代替|不当然|也不|并不|不宜|不能将|尚不|仍须另|须另|另行核验|另行判断|另据|不能推定|不能证明"
TOPIC = r"^[^，；：、]{4,22}(?:是|为|提供了|构成|属于|涉及|包括|来自|决定|影响|需要|要求|存在|体现为|表现为|成为|形成|具有|带来|意味着|在于)[^，；：、]{0,14}。$"
QLIST = r"(?:[一-鿿]{2,8}(?:负责|审核|核实|承担|决定|回答|处理|提供|记录|说明|解决)(?:什么|哪些|谁|如何|怎样)[、，]){2,}"
PARA3 = r"[一-鿿]{2,6}(?:什么|哪些|如何|怎样|是否)[、，][一-鿿]{2,6}(?:什么|哪些|如何|怎样|是否)[、，]"
CONN = r"^(?:因此|因而|由此|所以|这意味着|正因|换言之|也就是说|但|然而|不过|反之|相应地|进而|于是|可见|这表明|这说明|其中|就.{1,6}而言|与此|同样|相比之下|例如|比如|一方面|另一方面|不仅|即便|即使|尽管|虽然|如果|若)"


def body(t):
    t = re.sub(r"<!--.*?-->", "", t, flags=re.S)
    t = t.split("\n[^1]:")[0]
    t = re.sub(r"^\[\^[A-Za-z0-9]+\]:.*$", "", t, flags=re.M)
    t = re.sub(r"\[\^[A-Za-z0-9]+\]", "", t)
    return t


def paras(t):
    return [p.strip() for p in re.split(r"\n\s*\n", t) if p.strip() and not p.lstrip().startswith(("#", "|", "**表", "  ", "-", "![", "["))]


def sents(p):
    return [s.strip() for s in re.split(r"(?<=[。！？])", p) if len(re.findall(r"[一-鿿]", s)) >= 4]


def cjk(s):
    return len(re.findall(r"[一-鿿]", s))


def metrics(t):
    t = body(t)
    P = paras(t)
    S = [s for p in P for s in sents(p)]
    n = max(1, cjk(t)) / 10000
    sc = [len(sents(p)) for p in P]
    return {
        "字数": cjk(t),
        "防御否定/万字": round(len(re.findall(DEF, t)) / n, 1),
        "段末否定%": round(sum(1 for p in P if re.search(r"(不|无|非|未)[^。]{0,25}。$", p)) / max(1, len(P)) * 100, 1),
        "裸主题句段%": round(sum(1 for p in P if len(sents(p)) >= 2 and re.match(TOPIC, sents(p)[0]) and cjk(sents(p)[0]) <= 22) / max(1, len(P)) * 100, 1),
        "短首句段%": round(sum(1 for p in P if len(sents(p)) >= 2 and cjk(sents(p)[0]) <= 18 and "，" not in sents(p)[0]) / max(1, len(P)) * 100, 1),
        "疑问并列/万字": round((len(re.findall(QLIST, t)) + len(re.findall(PARA3, t))) / n, 2),
        "句首连接词%": round(sum(1 for s in S if re.search(CONN, s)) / max(1, len(S)) * 100, 1),
        "这字起句%": round(sum(1 for s in S if re.match(r"[“\"(（]*(?:这|对这|围绕这)", s)) / max(1, len(S)) * 100, 1),
        "还涉及类/万字": round(len(re.findall(r"还涉及|也涉及|还可以|也可以|还需要|也需要", t)) / n, 1),
        "句数CV": round(st.pstdev(sc) / st.mean(sc), 2) if len(sc) > 1 and st.mean(sc) else 0,
        "句长中位": st.median([cjk(s) for s in S]) if S else 0,
    }


def table(rows, names):
    keys = [k for k in rows[0] if k != "字数"]
    print("| 指标 | " + " | ".join(names) + " |")
    print("|---|" + "---|" * len(names))
    for k in keys:
        print(f"| {k} | " + " | ".join(str(r[k]) for r in rows) + " |")


def main():
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    if a[0] == "--openers":
        t = body(open(a[1], encoding="utf-8").read())
        S = [s for p in paras(t) for s in sents(p)]
        c = Counter(re.sub(r"^[“\"(（]*", "", s)[:2] for s in S)
        for k, v in c.most_common(15):
            print(f"{k}  {v/len(S)*100:.1f}%")
        return
    if a[0] == "--list":
        t = body(open(a[1], encoding="utf-8").read())
        for p in paras(t):
            ss = sents(p)
            if ss and len(ss) >= 2 and re.match(TOPIC, ss[0]) and cjk(ss[0]) <= 22:
                print("〔裸主题句〕", ss[0])
            for s in ss:
                if re.search(DEF, s):
                    print("〔防御〕", s)
            if re.search(r"(不|无|非|未)[^。]{0,25}。$", p):
                print("〔段末否定〕", ss[-1] if ss else p[-40:])
        return
    if a[0] == "--corpus":
        files = glob.glob(a[1].rstrip("/") + "/*.md")
        ms = [metrics(open(f, encoding="utf-8", errors="ignore").read()) for f in files]
        ms = [m for m in ms if m["字数"] >= 3000]
        target = metrics(open(a[2], encoding="utf-8").read())
        print(f"corpus n={len(ms)}")
        print("| 指标 | 本稿 | Q1 | 中位 | Q3 | 位置 |")
        print("|---|---|---|---|---|---|")
        for k in target:
            if k == "字数":
                continue
            vals = sorted(m[k] for m in ms)
            q1, md, q3 = vals[len(vals) // 4], vals[len(vals) // 2], vals[3 * len(vals) // 4]
            pos = sum(1 for v in vals if v <= target[k]) / len(vals) * 100
            flag = "↑" if target[k] > q3 else ("↓" if target[k] < q1 else "")
            print(f"| {k} | {target[k]} | {q1} | {md} | {q3} | P{pos:.0f} {flag} |")
        return
    rows = [metrics(open(f, encoding="utf-8").read()) for f in a]
    table(rows, [f.split("/")[-1][:18] for f in a])


if __name__ == "__main__":
    main()
