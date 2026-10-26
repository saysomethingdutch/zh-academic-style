#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""desplice.py — undo the two mechanical overshoots of a model cohesion pass.

1. Over-long sentences: for sentences ≥ LONG chars that contain "；" joining two
   independent clauses (each side ≥ MINCL chars and the right side starts a new
   clause rather than a list item), replace that "；" with "。". Never touches
   "：…；…；…" enumerations (colon before the first semicolon) or table/quote text.
2. "因此" inflation: keep at most one sentence-initial 因此/因而/由此/所以 per
   paragraph; later ones are dropped (the claim stays). Also drop "因此，" when it
   opens a paragraph (nothing to follow from).

Prints counts; writes in place when --write. Footnote markers/defs untouched.
"""
import re
import sys
from pathlib import Path

LONG, MINCL = 85, 26
CAUSAL = r"(因此|因而|由此|所以)，"


def cjk(s):
    return len(re.findall(r"[一-鿿]", s))


def split_para(p):
    sents = re.split(r"(?<=[。！？])", p)
    out = []
    n_split = 0
    for s in sents:
        if cjk(s) >= LONG and "；" in s and not re.search(r"：[^；]*(?:其一|一是|第一|（一）|首先)", s.split("；")[0]):
            parts = s.split("；")
            buf = parts[0]
            for q in parts[1:]:
                # right side must look like an independent clause: long enough and not starting with a list cue
                left = buf.split("。")[-1]
                left = left.split("：")[-1] if "：" in left else left
                if cjk(left) >= MINCL and cjk(q) >= MINCL and not re.match(r"^(其[一二三四五]|[一二三四五六七八九十]是|[（(][一二三四五六七八九十]|第[一二三四五六七八九十]|或者|或|及|和|与|以及|后者|前者)", q):
                    buf += "。" + q
                    n_split += 1
                else:
                    buf += "；" + q
            s = buf
        out.append(s)
    return "".join(out), n_split


CAUSE_MARK = r"由于|因为|一旦|若|如果|导致|使得|意味着|取决于|只要|凡|倘若|既然"


def thin_causal(p):
    """Drop sentence-initial 因此 when (a) it opens the paragraph, (b) a previous sentence in the
    paragraph already opened with 因此, or (c) it is the paragraph's last sentence and the preceding
    sentence states no cause (the '…。因此，X应当…' tail). Also collapse '因此，由于' -> '由于'."""
    sents = [s for s in re.split(r"(?<=[。！？])", p) if s]
    seen = 0
    n = 0
    out = []
    for i, s in enumerate(sents):
        m = re.match(r"^(\s*)" + CAUSAL, s)
        if m:
            prev = sents[i - 1] if i else ""
            last = i == len(sents) - 1
            if re.match(r"^\s*" + CAUSAL + r"由于", s):
                s = m.group(1) + s[m.end():]; n += 1
            elif i == 0 or seen >= 1 or (last and not re.search(CAUSE_MARK, prev)):
                s = m.group(1) + s[m.end():]; n += 1
            else:
                seen += 1
        out.append(s)
    return "".join(out), n


def split_enum(p):
    """'：其一，…；其二，…；其三，…' inside a ≥100-char sentence -> separate sentences."""
    sents = re.split(r"(?<=[。！？])", p)
    out = []; n = 0
    for s in sents:
        if cjk(s) >= 100:
            s2 = re.sub(r"；(?=(?:其[二三四五六]|第[二三四五六]|二是|三是|四是|五是|另一方面|在[一-鿿]{1,4}端|在[一-鿿]{2,6}上)[，、])", "。", s)
            if s2 != s:
                n += s.count("；") - s2.count("；"); s = s2
        out.append(s)
    return "".join(out), n


def process(text):
    body, _, fn = text.partition("\n[^")
    paras = body.split("\n\n")
    tot_split = tot_causal = 0
    newp = []
    for p in paras:
        if not p.strip() or p.lstrip().startswith(("#", "|", "**表", "  ", "-", "![", "<!--")) or re.match(r"^\s*-{3,}", p):
            newp.append(p)
            continue
        q, a = split_para(p)
        q, a2 = split_enum(q)
        a += a2
        q, b = thin_causal(q)
        tot_split += a
        tot_causal += b
        newp.append(q)
    return "\n\n".join(newp) + (("\n[^" + fn) if fn else ""), tot_split, tot_causal


def main():
    write = "--write" in sys.argv
    files = [a for a in sys.argv[1:] if not a.startswith("--")]
    for f in files:
        t = Path(f).read_text(encoding="utf-8")
        new, a, b = process(t)
        print(f"{f}: split {a} semicolons, dropped {b} 因此")
        if write and new != t:
            Path(f).write_text(new, encoding="utf-8")


if __name__ == "__main__":
    main()
