#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""并列项密度统计器（不分隔符）。

用法：
    python3 enum_stats.py <范文目录>            # 建基准
    python3 enum_stats.py <我的稿.md>           # 测待改稿
    python3 enum_stats.py <我的稿.md> --list    # 逐条列出，供人工四分类

为什么需要这个脚本：style_stats.py 的顿号指标会系统性漏报。
中文的三项并列最常写成「A、B和C」——**只有一个顿号**。
按"顿号≥3 的句子"统计，所有三项并列全部隐身，而三项并列恰恰是
报菜名最高频的形态。实测某稿顿号口径 5.7%（达标），
本口径 38.2%（高于同领域 26 篇中的 22 篇）。

本脚本按"读者读到几项"计数，不管作者用的是顿号、逗号还是"与/和/以及"。

已知假阳性（约占命中的 15%，判读时人工剔除）：
  · 复句被误判：「未必构成释放，……也不足以认定技术已经释放」
  · 时序叙述：「用户发送请求，模型在服务器上运行，输出经网络返回」
  · 路线图：「先……再……继而……最后……」
  · 对举：「既覆盖境内的外国国民，也覆盖境外的外国国民」
所以本脚本的数字是**上界**，不是判决。逐条看过再下结论。
"""
import re, sys, os, glob, statistics as st

# 段落最小长度，两条提取路径共用，**不要单独调低**。
# 曾试过降到 20，理由是它会滤掉真实的单句段（中文常见 20–60 字）。
# 结果：markdown 侧确实更准了，PDF 侧却把版面碎片当成段落——
# 语料单句段占比从 11.8% 暴涨到 39.6%，其中一篇 100%，基准直接报废。
# 结论：PDF 路径的 60 字下限是承重的（碎片与真实短段同样短，无法区分）。
# 代价是两侧都看不见 <60 字的段落，但**口径一致**，比较仍然成立：
# 该指标的准确读法是「≥60 字的单句段占比」。判断文档里的短段是否得当，
# 用 --shape 人眼看，不要靠这个数字。
MIN_PARA = 60

ZERO_WIDTH = '[​-‏﻿ 　]'

def norm(s):
    s = re.sub(ZERO_WIDTH, '', s)
    for _ in range(4):
        s = re.sub(r'([一-鿿，。；：、“”（）《》？！])\s+'
                   r'([一-鿿，。；：、“”（）《》？！])', r'\1\2', s)
    return s.strip()

def cjk(s):
    return len(re.findall(r'[一-鿿]', s)) / max(len(s), 1)

def paras_pdf(path):
    """与 style_stats.py 同法：按首行缩进判段，按字号剔除脚注。

    切勿改用 PDF 逐行导出的 .txt——那样量到的是版面行宽，不是句子。
    实测同一批论文，PDF 口径句长中位 54 字，.txt 口径 85 字，后者是假的。
    """
    import fitz
    doc = fitz.open(path); lines = []
    for pg in doc:
        for blk in pg.get_text("dict").get("blocks", []):
            for ln in blk.get("lines", []):
                t = norm("".join(sp["text"] for sp in ln.get("spans", [])))
                if not t:
                    continue
                sz = max((sp["size"] for sp in ln.get("spans", [])), default=0)
                lines.append((round(ln["bbox"][0], 1), t, round(sz, 1)))
    cand = [sz for _, t, sz in lines if cjk(t) > .5 and len(t) > 10]
    if not cand:
        return []
    body_size = max(set(cand), key=cand.count)
    body = [(x, t) for x, t, sz in lines
            if abs(sz - body_size) < .6 and cjk(t) > .35 and len(t) > 4]
    if not body:
        return []
    xs = [x for x, _ in body]
    left = max(set(xs), key=xs.count)
    out, buf = [], ""
    for x, t in body:
        if re.match(r'^[·\[]?\d+[·\]]?$', t) or t[0] in '①②③④⑤⑥⑦⑧⑨⑩':
            continue
        if x > left + 8 and buf:
            if len(buf) >= MIN_PARA:
                out.append(buf)
            buf = t
        else:
            buf += t
    if len(buf) >= MIN_PARA:
        out.append(buf)
    return out

# 脚注区的常见标题，逐个尝试切断（不同稿件用词不一，漏切会把上百条脚注当正文）
FN_HEADS = ('## 注释', '## 脚注', '## 参考文献', '## 参考资料', '# 注释', '# 脚注')

def paras_text(path):
    raw = open(path, encoding='utf-8', errors='ignore').read()
    for h in FN_HEADS:
        raw = raw.split(h)[0]
    out = []
    for line in raw.split('\n'):
        s = line.strip()
        # 脚注/参考文献定义必须在删除标记之前判断：若先删 [^98]，
        # "[^98]: 张凌寒…" 会变成 ": 张凌寒…"，此后再也识别不出（实测污染上百条）。
        if s.startswith('[^') or re.match(r'^\[\d+\]\s', s):
            continue
        p = norm(re.sub(r'\[\^[^\]]+\]', '', s))
        if len(p) < MIN_PARA or p.startswith(('#', '|', '>', '!', '```', ':', '：')):
            continue
        out.append(p)
    return out

ITEM = r'[一-鿿A-Za-z][^，。；：、（）]{1,14}'
PATS = [
    re.compile(r'(?:' + ITEM + r'、){2,}' + ITEM),                          # A、B、C
    re.compile(r'(?:' + ITEM + r'、)+' + ITEM + r'(?:和|与|以及|及|或)' + ITEM),  # A、B和C  ← 顿号口径漏的就是它
    re.compile(r'(?:' + ITEM + r'，){2,}(?:以及|和|与)?' + ITEM + r'[，。]'),      # A，B，C，
]

def hits(sent):
    """返回该句最长的并列串及项数（无则 None）。"""
    best, bn = None, 0
    for pt in PATS:
        for m in pt.finditer(sent):
            g = m.group(0)
            n = len(re.split(r'[、，]|和|与|以及|及|或', g))
            if n > bn:
                best, bn = g, n
    return (best, bn) if bn >= 3 else None

def analyse(paras):
    sents = [s for p in paras for s in re.split(r'(?<=[。；])', p) if len(s) > 15]
    rows = []
    for s in sents:
        h = hits(s)
        if h:
            rows.append((s, h[0], h[1]))
    n = max(len(sents), 1)
    return len(sents), rows, len(rows)/n*100, sum(1 for r in rows if r[2] >= 4)/n*100

def load(p):
    return paras_pdf(p) if p.lower().endswith('.pdf') else paras_text(p)

def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    listing = '--list' in sys.argv
    if not args:
        sys.exit(__doc__)
    files = []
    for a in args:
        if os.path.isdir(a):
            for e in ('*.pdf', '*.md', '*.txt', '*.docx'):
                files += sorted(glob.glob(os.path.join(a, e)))
        else:
            files += sorted(glob.glob(a))
    rows = []
    for f in files:
        try:
            ps = load(f)
        except Exception as e:
            print(f"  [跳过] {os.path.basename(f)[:40]} — {e}", file=sys.stderr); continue
        if len(ps) < 10:
            continue
        n, det, p3, p4 = analyse(ps)
        rows.append((os.path.basename(f), n, p3, p4, det))
    for name, n, p3, p4, det in sorted(rows, key=lambda r: r[2]):
        print(f"{name[:38]:<40}句{n:>5}  并列≥3 {p3:>5.1f}%   ≥4 {p4:>5.1f}%")
    if len(rows) > 1:
        v = [r[2] for r in rows]
        print(f"\n均值 {st.mean(v):.1f}%   中位 {st.median(v):.1f}%   范围 {min(v):.1f}–{max(v):.1f}")
    if listing:
        for name, n, p3, p4, det in rows:
            print(f"\n{'='*72}\n{name}  ({len(det)}/{n} = {p3:.1f}%)\n{'='*72}")
            print("逐条标记：【引】法条判例原文 /【骨】定义要件框架 /【凑】自造例举 /【误】假阳性")
            for i, (s, g, k) in enumerate(det, 1):
                print(f"\n[{i:>3}] ({k}项) 〔{g[:48]}〕\n      {s.strip()}")

if __name__ == '__main__':
    main()
