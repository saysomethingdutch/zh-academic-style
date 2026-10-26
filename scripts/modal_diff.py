#!/usr/bin/env python3
"""modal_diff: compare a section before/after a style pass.

Checks that a style rewrite did not change substance:
  - footnote markers: same multiset, same order
  - footnote definitions: identical text
  - numbers, article numbers (第N条), percentages, years: same multiset
  - quoted strings “…”: every quote in the original still present verbatim
  - book/article titles 《…》: same multiset
  - modal strength: per-sentence alignment (fuzzy) and report 不能→难以, 应→必须 etc.
  - new strong-claim words: 必然 / 唯一 / 本质在于 / 证明无效 / 根本上 / 不可避免
  - filler phrases introduced
Also prints the style metrics that the pass is meant to move.

Usage: modal_diff.py BEFORE.md AFTER.md [--json out.json]
Exit 1 when a hard check fails.
"""
import difflib
import json
import re
import statistics as st
import sys
from collections import Counter

SOFTEN = [("不能", "难以"), ("不能", "较难"), ("不得", "不宜"), ("应当", "宜"), ("应", "宜"), ("必须", "应"), ("必须", "需要"),
          ("不能", "不宜"), ("禁止", "避免"), ("不得", "避免"), ("无法", "难以"), ("不是", "并非完全")]
HARDEN = [("可以", "应当"), ("可", "须"), ("可", "应"), ("应", "必须"), ("应当", "必须"), ("需要", "必须"), ("可能", "必然"),
          ("可能", "会"), ("有助于", "能够"), ("可以", "必须"), ("宜", "应当")]
STRONG_NEW = r"必然|唯一|唯有|只有.{1,12}才|由此可见|可见，|综上|本质在于|深层实质|证明无效|根本上|不可避免|毫无疑问|无疑|显然|彻底|根本性|决定性"
FILLER = r"需要指出的是|值得注意的是|不难发现|不言而喻|基于这一|在.{1,8}语境下|以确保|正如.{1,12}所示|换言之，这|从根本上说|综上所述|总而言之|可以说|事实上|实际上|不可否认|众所周知|毋庸置疑"
DEFENSE = r"不构成|不等于|不能据此|不能直接|不能仅|不能简单|不足以|仅说明|只说明|不作为|并非|不意味着|不应据此|不能替代|不能代替|不当然|也不|并不|不宜|不能将|尚不|仍须另|须另|另行核验|另行判断|另据|不能推定|不能证明"
CONN = r"^(?:因此|因而|由此|所以|这意味着|正因|换言之|也就是说|但|然而|不过|反之|相应地|进而|于是|可见|这表明|这说明|其中|就.{1,6}而言|与此|同样|相比之下|例如|比如|一方面|另一方面|不仅|即便|即使|尽管|虽然|如果|若)"
TOPIC = r"^[^，；：、]{4,22}(?:是|为|提供了|构成|属于|涉及|包括|来自|决定|影响|需要|要求|存在|体现为|表现为|成为|形成|具有|带来|意味着|在于)[^，；：、]{0,14}。$"
QLIST = r"(?:[一-鿿]{2,8}(?:负责|审核|核实|承担|决定|回答|处理|提供|记录|说明|解决)(?:什么|哪些|谁|如何|怎样)[、，]){2,}"
PARA3 = r"[一-鿿]{2,6}(?:什么|哪些|如何|怎样|是否)[、，][一-鿿]{2,6}(?:什么|哪些|如何|怎样|是否)[、，]"
MODALS = ["必须", "应当", "应", "须", "不得", "不能", "禁止", "可以", "可", "宜", "需要", "可能", "难以", "无法"]


def split_fn(t):
    m = re.search(r"\n\[\^[A-Za-z0-9]+\]:", t)
    if not m:
        return t, ""
    return t[: m.start()], t[m.start():]


def body_only(t):
    t = re.sub(r"<!--.*?-->", "", t, flags=re.S)
    t = re.sub(r"<!-- 改动说明.*", "", t, flags=re.S)
    return t


def paras(t):
    return [p.strip() for p in re.split(r"\n\s*\n", t) if p.strip() and not p.lstrip().startswith(("#", "|", "**表", "  ", "-", "!["))]


def sents(p):
    return [s.strip() for s in re.split(r"(?<=[。！？])", p) if len(re.findall(r"[一-鿿]", s)) >= 4]


def cjk(t):
    return len(re.findall(r"[一-鿿]", t))


def metrics(t):
    P = paras(t)
    S = [s for p in P for s in sents(p)]
    n = cjk(t) / 10000
    pl = [cjk(p) for p in P]
    sc = [len(sents(p)) for p in P]
    m = {
        "字数": cjk(t), "段数": len(P),
        "防御否定/万字": round(len(re.findall(DEFENSE, t)) / n, 1),
        "段末否定%": round(sum(1 for p in P if re.search(r"(不|无|非|未)[^。]{0,25}。$", p)) / max(1, len(P)) * 100, 1),
        "句首连接词%": round(sum(1 for s in S if re.search(CONN, s)) / max(1, len(S)) * 100, 1),
        "段长CV": round(st.pstdev(pl) / st.mean(pl), 2) if len(pl) > 1 else 0,
        "句数CV": round(st.pstdev(sc) / st.mean(sc), 2) if len(sc) > 1 else 0,
        "句长中位": st.median([cjk(s) for s in S]) if S else 0,
        "三项并列/万字": round(len(re.findall(r"[一-鿿]{2,8}、[一-鿿]{2,8}[、和与及或]+[一-鿿]{2,8}", t)) / n, 1),
        "填充语": len(re.findall(FILLER, t)),
        "强断言词": len(re.findall(STRONG_NEW, t)),
        "序号分项": len(re.findall(r"其[一二三四五]|（[一二三四五六七八九十]）", t)),
        "这字起句%": round(sum(1 for s in S if re.match(r"[“\"(（]*(?:这|对这|围绕这)", s)) / max(1, len(S)) * 100, 1),
        "还涉及类/万字": round(len(re.findall(r"还涉及|也涉及|还可以|也可以|还需要|也需要", t)) / n, 1),
        "段内这字起句≥2": sum(1 for p in P if sum(1 for s in sents(p) if re.match(r"[“\"(（]*(?:这|对这|围绕这)", s)) >= 2),
        "裸主题句段%": round(sum(1 for p in P if len(sents(p)) >= 2 and re.match(TOPIC, sents(p)[0]) and cjk(sents(p)[0]) <= 22) / max(1, len(P)) * 100, 1),
        "短首句段%": round(sum(1 for p in P if len(sents(p)) >= 2 and cjk(sents(p)[0]) <= 18 and "，" not in sents(p)[0]) / max(1, len(P)) * 100, 1),
        "疑问并列": len(re.findall(QLIST, t)) + len(re.findall(PARA3, t)),
    }
    return m


def multiset_check(name, a, b, out, hard=True):
    ca, cb = Counter(a), Counter(b)
    lost = list((ca - cb).elements())
    added = list((cb - ca).elements())
    if lost or added:
        out["issues"].append({"check": name, "lost": lost[:30], "added": added[:30], "hard": hard})
        return not hard
    return True


def main():
    a_path, b_path = sys.argv[1], sys.argv[2]
    A = body_only(open(a_path, encoding="utf-8").read())
    B = body_only(open(b_path, encoding="utf-8").read())
    Ab, Af = split_fn(A)
    Bb, Bf = split_fn(B)
    out = {"issues": [], "modal_changes": [], "metrics_before": metrics(Ab), "metrics_after": metrics(Bb)}
    ok = True
    # footnote markers
    fa = re.findall(r"\[\^([A-Za-z0-9]+)\]", Ab)
    fb = re.findall(r"\[\^([A-Za-z0-9]+)\]", Bb)
    if fa != fb:
        ok &= multiset_check("脚注标记（顺序或数量）", fa, fb, out)
        if Counter(fa) == Counter(fb):
            out["issues"].append({"check": "脚注标记顺序改变", "hard": False})
    # footnote anchors: the 12 chars before each marker should still be found before the same marker after
    moved = []
    for k in set(fa):
        ma_ = re.search(r"([^\n]{0,12})\[\^%s\]" % re.escape(k), Ab)
        mb_ = re.search(r"([^\n]{0,12})\[\^%s\]" % re.escape(k), Bb)
        if ma_ and mb_:
            a_ctx = "".join(re.findall(r"[一-鿿A-Za-z0-9]", ma_.group(1)))[-6:]
            b_ctx = "".join(re.findall(r"[一-鿿A-Za-z0-9]", mb_.group(1)))[-6:]
            Bflat = "".join(re.findall(r"[一-鿿A-Za-z0-9\[\]\^]", Bb))
            if a_ctx and (a_ctx + "[^" + k + "]") not in Bflat:
                moved.append({"key": k, "before": ma_.group(1), "after": mb_.group(1)})
    if moved:
        out["issues"].append({"check": "脚注锚点改变（标记前文字不同）", "items": moved[:20], "hard": True}); ok = False
    # footnote defs
    da = dict(re.findall(r"^\[\^([A-Za-z0-9]+)\]:\s*(.*)$", Af, re.M))
    db = dict(re.findall(r"^\[\^([A-Za-z0-9]+)\]:\s*(.*)$", Bf, re.M))
    for k, v in da.items():
        if k not in db:
            out["issues"].append({"check": "脚注定义丢失", "key": k, "hard": True}); ok = False
        elif re.sub(r"\s", "", db[k]) != re.sub(r"\s", "", v):
            out["issues"].append({"check": "脚注定义被改", "key": k, "before": v[:80], "after": db[k][:80], "hard": True}); ok = False
    # numbers / articles / years / percents
    num = lambda t: re.findall(r"第[一二三四五六七八九十百零〇\d]+条(?:之[一二三])?(?![脉线路])|\d+(?:\.\d+)?%|\d{4}年|\d+(?:\.\d+)?[万亿]?[件篇条个次人家]", t)
    ok &= multiset_check("数字/条号/年份", num(Ab), num(Bb), out)
    # quotes
    qa = re.findall(r"“([^”]{4,})”", Ab)
    for q in qa:
        if q not in Bb:
            out["issues"].append({"check": "引文丢失或被改", "quote": q[:60], "hard": True}); ok = False
    # titles
    ok &= multiset_check("书名号", re.findall(r"《[^》]+》", Ab), re.findall(r"《[^》]+》", Bb), out, hard=False)
    # tables / headings
    ha = re.findall(r"^#{1,3} .*$", Ab, re.M); hb = re.findall(r"^#{1,3} .*$", Bb, re.M)
    if ha != hb:
        out["issues"].append({"check": "标题行改变", "before": ha, "after": hb, "hard": True}); ok = False
    ta = [l for l in Ab.split("\n") if l.startswith("|")]; tb = [l for l in Bb.split("\n") if l.startswith("|")]
    if [re.sub(r"\s", "", l) for l in ta] != [re.sub(r"\s", "", l) for l in tb]:
        out["issues"].append({"check": "表格改变", "hard": True}); ok = False
    # modal strength: align sentences
    SA = [s for p in paras(Ab) for s in sents(p)]
    SB = [s for p in paras(Bb) for s in sents(p)]
    sm = difflib.SequenceMatcher(None, SA, SB, autojunk=False)
    # fuzzy alignment: for each A sentence find best B sentence by ratio
    for sa in SA:
        best, bs = None, 0
        for sb in SB:
            r = difflib.SequenceMatcher(None, sa, sb).ratio()
            if r > bs:
                best, bs = sb, r
        if best is None or bs < 0.45:
            continue
        ma = Counter(re.findall("|".join(MODALS), sa)); mb = Counter(re.findall("|".join(MODALS), best))
        for x, y in SOFTEN:
            if ma[x] > mb[x] and mb[y] > ma[y]:
                out["modal_changes"].append({"type": "软化", "from": x, "to": y, "before": sa[:70], "after": best[:70]})
        for x, y in HARDEN:
            if ma[x] > mb[x] and mb[y] > ma[y]:
                out["modal_changes"].append({"type": "硬化", "from": x, "to": y, "before": sa[:70], "after": best[:70]})
    # new strong claims / filler
    sa_strong = Counter(re.findall(STRONG_NEW, Ab)); sb_strong = Counter(re.findall(STRONG_NEW, Bb))
    new_strong = list((sb_strong - sa_strong).elements())
    if new_strong:
        out["issues"].append({"check": "新增强断言词", "added": new_strong, "hard": False})
    fa_f = Counter(re.findall(FILLER, Ab)); fb_f = Counter(re.findall(FILLER, Bb))
    new_fill = list((fb_f - fa_f).elements())
    if new_fill:
        out["issues"].append({"check": "新增填充语", "added": new_fill, "hard": False})
    ma_, mb_ = out["metrics_before"], out["metrics_after"]
    if mb_["这字起句%"] > 5 or mb_["段内这字起句≥2"] > 0 or mb_["还涉及类/万字"] > 6:
        out["issues"].append({"check": "衔接词单调（这字起句/还涉及类超限）", "这字起句%": mb_["这字起句%"], "段内≥2": mb_["段内这字起句≥2"], "还涉及类/万字": mb_["还涉及类/万字"], "hard": False})
    para_conn = sum(1 for p in paras(Bb) if sum(1 for s in sents(p) if re.search(CONN, s)) > 2)
    out["metrics_after"]["段内连接词>2"] = para_conn
    if para_conn > 2 or mb_["句首连接词%"] > 15:
        out["issues"].append({"check": "连接词过量", "段内>2": para_conn, "句首连接词%": mb_["句首连接词%"], "hard": False})
    if mb_["裸主题句段%"] > 7 or mb_["疑问并列"] > 0:
        out["issues"].append({"check": "段首裸主题句/疑问并列超限", "裸主题句段%": mb_["裸主题句段%"], "疑问并列": mb_["疑问并列"], "hard": False})
    if abs(mb_["字数"] - ma_["字数"]) / max(1, ma_["字数"]) > 0.05:
        out["issues"].append({"check": "字数变化超过5%", "before": ma_["字数"], "after": mb_["字数"], "hard": False})
    out["hard_fail"] = not ok
    # print
    print(f"== modal_diff {a_path} -> {b_path}")
    mb, ma_ = out["metrics_before"], out["metrics_after"]
    print(f"{'指标':14s}{'改前':>8s}{'改后':>8s}")
    for k in mb:
        print(f"{k:14s}{str(mb[k]):>8s}{str(ma_[k]):>8s}")
    for i in out["issues"]:
        print(("HARD " if i.get("hard") else "warn ") + json.dumps(i, ensure_ascii=False)[:300])
    for c in out["modal_changes"]:
        print("MODAL " + json.dumps(c, ensure_ascii=False)[:260])
    print("RESULT:", "FAIL" if out["hard_fail"] else "PASS", f"modal_changes={len(out['modal_changes'])}")
    if "--json" in sys.argv:
        open(sys.argv[sys.argv.index("--json") + 1], "w", encoding="utf-8").write(json.dumps(out, ensure_ascii=False, indent=1))
    sys.exit(1 if out["hard_fail"] else 0)


if __name__ == "__main__":
    main()
