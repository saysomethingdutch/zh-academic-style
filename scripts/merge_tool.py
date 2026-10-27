#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""merge_tool.py — hand-driven paragraph merging + 因此 cleanup for one section.

  merge_tool.py show UNIT            numbered body paragraphs (sentence count, 因此 marks)
  merge_tool.py apply UNIT PLAN.json apply a plan:
     {"merge": [[3,4],[7,8,9]],          # groups of consecutive body-paragraph indices
      "seam": {"3": ["old text at seam", "new text"]},   # optional edit applied after merging group starting at 3
      "drop_yinci": [[5,0],[12,2]],      # [para index, nth 因此-sentence in that para] -> remove leading 因此，
      "edits": [["old","new"], ...]}     # free edits, applied last, must match exactly once
Only body paragraphs are indexed (headings, tables, notes skipped); merging across a heading is refused.
Writes final.md in place (backup final_v2.md once).
"""
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP = ("#", "|", "**表", "  ", "-", "![", "<!--", "注：", "注:", "资料来源")


def cjk(s):
    return len(re.findall(r"[一-鿿]", s))


def sents(p):
    return [s for s in re.split(r"(?<=[。！？])", p) if cjk(s) >= 2]


def load(unit):
    t = (ROOT / "sections" / unit / "final.md").read_text(encoding="utf-8")
    body, sep, fn = t.partition("\n[^")
    blocks = body.split("\n\n")
    return blocks, sep + fn


def is_body(b):
    s = b.strip()
    return bool(s) and not s.startswith(SKIP) and not re.match(r"^\*\*（[一二三四五六七八九十]+）", s) and not re.match(r"^-{3,}", s)


def show(unit):
    blocks, _ = load(unit)
    idx = 0
    for b in blocks:
        s = b.strip()
        if not s:
            continue
        if is_body(b):
            ss = sents(s)
            yc = [k for k, x in enumerate(ss) if x.lstrip().startswith(("因此", "因而", "由此", "所以"))]
            tag = f"[{idx}] ({len(ss)}句/{cjk(s)}字" + (f" 因此×{len(yc)}" if yc else "") + ")"
            print(tag, s)
            print()
            idx += 1
        else:
            print("    " + s.split("\n")[0][:80])
    print(f"-- {idx} body paragraphs")


def apply(unit, plan):
    d = ROOT / "sections" / unit
    if not (d / "final_v2.md").exists():
        shutil.copy(d / "final.md", d / "final_v2.md")
    blocks, fn = load(unit)
    # map body index -> block position
    pos = [i for i, b in enumerate(blocks) if is_body(b)]
    # drop 因此 first (indices refer to pre-merge numbering)
    for pi, nth in plan.get("drop_yinci", []):
        b = blocks[pos[pi]]
        ss = sents(b)
        hits = [k for k, x in enumerate(ss) if x.lstrip().startswith(("因此", "因而", "由此", "所以"))]
        k = hits[nth]
        ss[k] = re.sub(r"^(\s*)(因此|因而|由此|所以)，", r"\1", ss[k], 1)
        blocks[pos[pi]] = "".join(ss)
    # merges: process groups from the end so positions stay valid
    groups = sorted(plan.get("merge", []), key=lambda g: g[0], reverse=True)
    for g in groups:
        assert g == list(range(g[0], g[-1] + 1)), f"group must be consecutive body indices: {g}"
        p0, p1 = pos[g[0]], pos[g[-1]]
        between = blocks[p0:p1 + 1]
        assert all(is_body(x) for x in between if x.strip()), f"heading/table inside merge group {g}"
        merged = "".join(x.strip() for x in between if x.strip())
        seam = plan.get("seam", {}).get(str(g[0]))
        if seam:
            assert merged.count(seam[0]) == 1, f"seam text not unique/found for group {g}: {seam[0][:30]}"
            merged = merged.replace(seam[0], seam[1])
        blocks[p0:p1 + 1] = [merged]
    text = "\n\n".join(blocks) + fn
    for old, new in plan.get("edits", []):
        assert text.count(old) == 1, f"edit text not unique/found: {old[:40]}"
        text = text.replace(old, new)
    (d / "final.md").write_text(text, encoding="utf-8")
    bl = [b for b in text.partition("\n[^")[0].split("\n\n") if is_body(b)]
    sc = [len(sents(b)) for b in bl]
    import statistics as st
    print(f"{unit}: {len(pos)} -> {len(bl)} paragraphs; 句数CV {st.pstdev(sc)/st.mean(sc):.2f}; 8句+ {sum(1 for x in sc if x>=8)}; 因此起句 {sum(1 for b in bl for s in sents(b) if s.lstrip().startswith('因此'))}")


if __name__ == "__main__":
    if sys.argv[1] == "show":
        show(sys.argv[2])
    else:
        apply(sys.argv[2], json.loads(Path(sys.argv[3]).read_text(encoding="utf-8")))
