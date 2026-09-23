#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""逐词回测：这个词到底是"学界通用语"，还是"某一个人的口头禅"？

用法：
    python3 word_check.py <语料目录> 词1 词2 …
    python3 word_check.py <语料目录> --file <我的稿.md> 词1 词2 …   # 附带本稿频次对比
    加 --substring 退回子串计数（不推荐，实测虚高 0–25%）

为什么不能只看总频次：
    「溢出」在 345 篇里出现 42 次，看着不低——其中 34 次出自同一位作者（81%）。
    「传导」41 次，李伯轩 18 次 + 霍政欣 9 次 = 66%。
    这类词的"高频"是一两个人的写作习惯，不是领域惯例，**不能拿来当范本**。
    反过来「依据」2221 次分布在 56/58 位作者身上（最高占比 18%），才是共同语言。

三分法（输出里的"判定"列）：
    语料 0 次                        → 禁用成立，这是唯一能说"中文论文不用"的情形
    ≥8 位作者且最高占比 <30%          → 通用或至少不禁忌，只能说"少用"
    最高一位占比 ≥60%                 → 个人语癖：既不该禁，也不该学

作者名从文件名末段解析（`标题_作者.md`），解析不出的归入 '?'。
"""
import sys, os, re
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mineru_body import body_paras, expand

# ── 计数方式：默认按「真实成词」，不是子串 ───────────────────────────
# 子串计数会把词内部的片段算进去。实测虚高率：分层 25%（"划分层级"）、
# 入口 20%（"切入口"）、闭环 11%、衔接 9%，其余多数为 0%。
# 偏差不大，但方向不定，且随词而变——所以能用分词就用分词。
try:
    import jieba
    jieba.setLogLevel(60)
    _HAS_JIEBA = True
except ImportError:
    _HAS_JIEBA = False

_SEG_CACHE = {}

def count_word(text, w, exact=True):
    """exact=True 用分词计数；无 jieba、exact=False、或该词本身被切开时退回子串。

    ⚠ 分词计数靠 `t == w` 匹配单个词元。若 w 本身被 jieba 切成多个词元
    （「人格利益」→ 人格/利益，「归属判断」→ 归属/判断），就没有任何词元能等于 w，
    计数恒为 0——而脚本会把这个 0 印成「★语料 0 次，禁用成立」，也就是说
    **对任何词典外的多字短语，最强的那条判定都是结构性假阴性**。
    2026-09 实测（民法所 387 篇）：人格利益 子串 185 次/26 篇、人格要素 21/5、
    归属判断 3/3，分词一律报 0。同一批里 自我呈现、社会形象、显性标识 子串也是 0，
    那三个才是真的 0——两者在旧口径下完全无法区分。
    多字短语因而改走子串：词越长，被当成更长词内部片段的概率越低，
    这点偏差远小于"恒为 0"的代价。
    """
    if not (exact and _HAS_JIEBA):
        return text.count(w), False
    if len(list(jieba.cut(w))) > 1:
        return text.count(w), False
    key = id(text)
    if key not in _SEG_CACHE:
        _SEG_CACHE[key] = list(jieba.cut(text))
    return sum(1 for t in _SEG_CACHE[key] if t == w), True


def load_corpus(root):
    docs = []
    for f in expand([root]):          # 跳过 root 之下名为 tmp 的子目录，见 mineru_body.in_tmp
        ps = body_paras(f)
        if len(ps) < 15:
            continue
        au = os.path.basename(f)[:-3].split('_')[-1]
        au = re.sub(r'[（(].*?[)）]|\d', '', au).strip()
        docs.append((au if au and len(au) <= 4 else '?', ''.join(ps)))
    return docs


def verdict(tot, n_au, top_share):
    """判定顺序很关键：先看作者数，再看集中度。

    曾经把集中度放在前面，结果「衔接」（22 位作者用过）因为最高一位占 63%
    被判成"个人语癖"——22 个人在用的词显然不是某一个人的口头禅。
    个人语癖必须同时满足**作者少**且**集中度高**。
    """
    if tot == 0:
        return '★语料 0 次，禁用成立'
    if n_au >= 8:
        return '多人使用，不能判禁用' if top_share < 40 else '多人用但有主力作者，可用'
    if top_share >= 60:
        return '个人语癖，不该学也不必禁'
    return '少数人用，慎用'


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if len(args) < 2:
        sys.exit(__doc__)
    root, words = args[0], args[1:]
    mine = None
    if '--file' in sys.argv:
        i = sys.argv.index('--file')
        mine_path = sys.argv[i + 1]
        words = [w for w in words if w != mine_path]
        raw = open(mine_path, encoding='utf-8').read()
        for h in ('## 注释', '## 脚注', '## 参考文献'):
            raw = raw.split(h)[0]
        mine = ''.join(l for l in raw.split('\n')
                       if not l.lstrip().startswith(('#', '[^', '>', '|')))
    exact = '--substring' not in sys.argv
    if exact and not _HAS_JIEBA:
        print("⚠ 未装 jieba，退回子串计数；实测虚高 0–25%，见脚本注释。\n", file=sys.stderr)
    docs = load_corpus(root)
    Z = sum(len(re.findall(r'[一-鿿]', t)) for _, t in docs)
    if Z == 0:
        sys.exit(f"语料目录里没有可用的 md（正文段 ≥15 的 MinerU 解析稿）：{root}")
    n_doc = len(docs)
    n_all_au = len({a for a, _ in docs})
    mz = len(re.findall(r'[一-鿿]', mine)) if mine else 0
    print(f"语料 {n_doc} 篇 / {n_all_au} 位作者 / {Z} 汉字"
          + (f"　　本稿 {mz} 汉字" if mine else "") + "\n")
    hdr = f"{'词':<8}{'总次':>5}{'/万字':>8}{'作者数':>7}{'最高占比':>8}"
    if mine:
        hdr += f"{'本稿':>6}{'/万字':>8}"
    print(hdr + "   判定")
    print("-" * (len(hdr) + 34))
    for w in words:
        per = defaultdict(int)
        for a, t in docs:
            c, _ = count_word(t, w, exact)
            per[a] += c
        per = {k: v for k, v in per.items() if v}
        tot = sum(per.values())
        top = max(per.values()) / tot * 100 if tot else 0.0
        line = f"{w:<8}{tot:>5}{tot/Z*10000:>8.2f}{len(per):>7}{(f'{top:.0f}%' if tot else '—'):>8}"
        if mine:
            mn, _ = count_word(mine, w, exact)
            line += f"{mn:>6}{mn/max(mz,1)*10000:>8.2f}"
        print(line + f"   {verdict(tot, len(per), top)}")
        if tot:
            top6 = sorted(per.items(), key=lambda x: -x[1])[:6]
            print(f"{'':<8}谁在用：" + "、".join(f"{k}{v}" for k, v in top6)
                  + ("…" if len(per) > 6 else ""))


if __name__ == '__main__':
    main()
