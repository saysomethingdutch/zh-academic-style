#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cohesion_gate.py — post-process a Gemini cohesion rewrite and produce a gate report.

Automatic fixes (safe, mechanical):
  - strip the <!-- 改动说明 --> block to a side file
  - restore the footnote definition block verbatim from the source final.md
  - strong-word softening: 由此可见，X → X ; 可见，X → X ; 综上，X → X ;
    唯有A，B才C → A，B才C is NOT safe → listed for hand review instead
  - drop stray markdown like trailing "**" lines Gemini sometimes emits
Hand-review list (written to gate_report.md):
  - footnote anchors that moved to a different claim (from modal_diff)
  - 唯有/只有…才/必然/本质在于 occurrences with context
  - paragraphs with >2 sentence-initial connectors
  - word count delta > 8%
  - any HARD modal_diff failure other than anchors
Exit 0 always; the report says whether the section is auto-approvable.

Usage: cohesion_gate.py --section ch1_s4 --rewrite cohesion/rewrite_gemini.md
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from modal_diff import CONN, metrics, paras, sents  # noqa

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
STRONG_CTX = r"[^。]{0,40}(?:唯有|只有[^。]{1,12}才|必然|本质在于|深层实质|不可避免|毫无疑问)[^。]{0,40}。"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--section", required=True)
    ap.add_argument("--rewrite", default="cohesion/rewrite_gemini.md")
    ap.add_argument("--src", default="final.md")
    a = ap.parse_args()
    d = ROOT / "sections" / a.section
    w = d / "cohesion"
    src = (d / a.src).read_text(encoding="utf-8")
    rw = (d / a.rewrite).read_text(encoding="utf-8")

    # split notes
    notes = re.search(r"<!-- 改动说明 -->.*?<!-- 改动说明结束 -->", rw, re.S)
    body = rw[: notes.start()] if notes else rw
    if notes:
        (w / "notes_gemini.md").write_text(notes.group(0), encoding="utf-8")
    # restore footnote block
    m_src = re.search(r"\n\[\^[A-Za-z0-9]+\]:", src)
    body = re.split(r"\n\[\^[A-Za-z0-9]+\]:", body, 1)[0].rstrip() + "\n"
    if m_src:
        body += src[m_src.start():].rstrip() + "\n"
    # mechanical softening
    auto = []
    for pat, rep in [(r"由此可见，", ""), (r"(?<![一-鿿])可见，", ""), (r"综上所述，", ""), (r"综上，", ""), (r"总而言之，", "")]:
        n = len(re.findall(pat, body))
        if n:
            body = re.sub(pat, rep, body)
            auto.append(f"删去「{pat.replace('(?<![一-鿿])', '')}」{n} 处")
    # capitalise sentence after removal: nothing needed in Chinese
    body = re.sub(r"\n\*\*\s*\n", "\n", body)
    body = re.sub(r"\n{3,}", "\n\n", body)
    (w / "gated.md").write_text(body, encoding="utf-8")

    # modal_diff on gated
    r = subprocess.run([PY, str(ROOT / "pipeline/modal_diff.py"), str(d / a.src), str(w / "gated.md"), "--json", str(w / "modal_diff_gated.json")], capture_output=True, text=True)
    md = json.loads((w / "modal_diff_gated.json").read_text(encoding="utf-8"))

    hand = []
    for i in md["issues"]:
        if i["check"].startswith("脚注锚点"):
            for it in i["items"]:
                hand.append(f"脚注 [^{it['key']}] 锚点移动：原「…{it['before']}」→ 现「…{it['after']}」")
        elif i.get("hard"):
            hand.append(f"硬校验未过：{json.dumps(i, ensure_ascii=False)[:200]}")
    for mc in md["modal_changes"]:
        hand.append(f"情态{mc['type']} {mc['from']}→{mc['to']}：{mc['before'][:50]}")
    for s in re.findall(STRONG_CTX, body):
        hand.append(f"强断言：{s.strip()}")
    for p in paras(body):
        c = sum(1 for s in sents(p) if re.search(CONN, s))
        if c > 2:
            hand.append(f"连接词 {c} 处的段：{p[:60]}…")
    ma, mb = md["metrics_before"], md["metrics_after"]
    delta = (mb["字数"] - ma["字数"]) / max(1, ma["字数"])
    if abs(delta) > 0.08:
        hand.append(f"字数变化 {delta:+.1%}（{ma['字数']}→{mb['字数']}）")

    approvable = not any(h.startswith(("脚注", "硬校验", "情态", "强断言")) for h in hand)
    rep = [f"# gate report — {a.section}", "", f"自动处理：{'；'.join(auto) or '无'}", "",
           f"指标：防御否定 {ma['防御否定/万字']}→{mb['防御否定/万字']}；段末否定 {ma['段末否定%']}→{mb['段末否定%']}；裸主题句段 {ma['裸主题句段%']}→{mb['裸主题句段%']}；句首连接词 {ma['句首连接词%']}→{mb['句首连接词%']}；句长中位 {ma['句长中位']}→{mb['句长中位']}；字数 {ma['字数']}→{mb['字数']}", "",
           f"**{'可自动通过' if approvable else '需人工处理'}**（{len(hand)} 项）", ""]
    rep += [f"- {h}" for h in hand]
    (w / "gate_report.md").write_text("\n".join(rep) + "\n", encoding="utf-8")
    (w / "gate_status.json").write_text(json.dumps({"approvable": approvable, "hand_items": len(hand), "delta": round(delta, 3)}, ensure_ascii=False), encoding="utf-8")
    print(a.section, "APPROVABLE" if approvable else "HAND", len(hand), f"{delta:+.1%}")


if __name__ == "__main__":
    main()
