#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""中文摘要的结构与衔接：从 MinerU 语料建基准，并逐句诊断待改稿的摘要。

用法：
    python3 abstract_stats.py <语料目录>                         # 建摘要基准
    python3 abstract_stats.py <语料目录> --file <稿件.md>        # 另诊断稿件里「摘要：」那一行
    python3 abstract_stats.py <语料目录> --text "摘要全文"       # 直接给摘要
    python3 abstract_stats.py <语料目录> --dump abstracts.json   # 存下抽出的摘要，供人工翻看
    --exclude 子串1,子串2   剔除文件名含这些子串的稿件（学位论文、非法学文本等）

民法所基准（SKILL.md 第六节的数字）这样复现：
    python3 abstract_stats.py ~/skill-create/论文写作研究/民商经济法学院-民法所 \
        --exclude 电影融合营销,非对称冲突结构,动产有形交付的法律性质,强制执行立法研究,证券内幕交易民事责任研究

测什么：
  · 尺寸：字数（含标点）、句数（按。！？切）
  · 句首连接语：转折、承接问题、因果推论、递进顺承、让步、条件、总括、背景时间
  · 衔接：后句开头（前 14 字）是否重提前句的关键词，或以「这／该／此／上述……」指代起头；
          两句只在后句中后段才共享关键词的，算「句中相关」；一个共同关键词都没有的，算「断开」
  · 结构：首句是否交代问题或背景；以问题开头的，第 2–3 句用了什么过渡；
          末句是否规范性主张（应、宜、须、可以…）；有没有展望词（未来、有待、今后…）
  · 自指（本文、笔者、作者）、≥3 项并列

⚠ 关键词用 jieba.cut 取，**不做词性过滤**。实测词性标注会把「同意」标成副词 d，
  按「名、动、形」过滤就把它丢了，第 5→6 句因此被误报为「断开」。
  旧版（带词性过滤）同一语料的「开头接住」中位只有 50%，去掉过滤后是 67%。
"""
import sys, os, re, json
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mineru_body import expand

import jieba
jieba.setLogLevel(60)

# ── 抽摘要 ───────────────────────────────────────────────────────────
HEAD = re.compile(r'^\s*[\[【〔(（]?\s*(内\s*容\s*摘\s*要|内\s*容\s*提\s*要|摘\s*要|提\s*要)\s*[\]】〕)）]?\s*[:：]?\s*')
STOPLINE = re.compile(r'^\s*[\[【〔(（]?\s*(关\s*键\s*词|关键字|主题词|作\s*者|中图分类号|文献标识码|文章编号|DOI|Abstract|Key\s*words?|基金|收稿)', re.I)
HAN = re.compile(r'[一-鿿]')


def clean(s):
    s = re.sub(r'\$\^?\{?[①-⑳\d,\s*]{1,12}\}?\$', '', s)
    s = re.sub(r'[①-⑳]|\\\*|\*', '', s)
    s = re.sub(r'(?<=[一-鿿，。；：、“”（）《》])\s+|\s+(?=[一-鿿，。；：、“”（）《》])', '', s)   # MinerU 在中文间插的空格
    return s.strip()


def extract(root, exclude=()):
    out, seen = [], set()
    for f in expand([root]):
        if any(e in f for e in exclude):
            continue
        lines = open(f, encoding='utf-8', errors='ignore').read().split('\n')
        for i, line in enumerate(lines[:80]):
            m = HEAD.match(line.lstrip('# '))
            if not m:
                continue
            text = line.lstrip('# ')[m.end():]
            if len(HAN.findall(text)) < 20 and line.startswith('#'):      # 标题式「## 摘要」，正文在下一段
                text = next((l for l in lines[i + 1:i + 4] if l.strip()), '')
            elif len(line) < 40:
                continue
            for nxt in lines[i + 1:i + 6]:                                 # 摘要偶尔被切成两段
                if not nxt.strip():
                    continue
                if STOPLINE.match(nxt) or nxt.startswith('#'):
                    break
                if len(HAN.findall(nxt)) / max(len(nxt), 1) > 0.5:
                    text += nxt
                break
            text = clean(text)
            if len(HAN.findall(text)) < 60:
                continue
            if re.search(r'本文分为|全文共|分为[一二三四五六七八九十]+章|第一章', text) or len(text) > 900:
                break                                                      # 学位论文的分章摘要，体裁不同
            if text[:40] in seen:
                break
            seen.add(text[:40])
            au = re.sub(r'\.md$', '', os.path.basename(f)).split('_')[-1]
            au = re.sub(r'[（(].*?[)）]|\d', '', au).strip()
            out.append({'file': os.path.relpath(f, root), 'author': au if au and len(au) <= 4 else '?',
                        'abstract': text})
            break
    return out


# ── 句子与句首连接语 ─────────────────────────────────────────────────
CAT = [   # 按顺序取第一个命中
    ('转折', r'(但是?|然而|不过|可是|却|相反|反之)'),
    ('承接问题', r'(对此|为此|就此|对于(这一|上述|此|该)|针对(这一|上述|此|该)|基于此|有鉴于此|鉴于此|在此背景下|面对)'),
    ('因果推论', r'(因此|因而|所以|故而?|由此|从而|据此|可见|于是|是故|是以|这就要求|这意味着|这表明|这说明)'),
    ('递进顺承', r'(此外|另外|同时|进而|进一步|而且|并且|在此基础上|以此为基点|再者|其次|首先|最后|其一|其二|其三|一方面|另一方面|第一|第二|第三|与此同时|当然|具体而言|具体来说|详言之|申言之)'),
    ('让步', r'(虽然|尽管|固然|诚然|即使|即便)'),
    ('条件', r'(若|如果|倘若|假如|只有|唯有|只要)'),
    ('总括', r'(总之|综上|总体而言|概言之|简言之|总的来说|总的来看|整体而言)'),
    ('背景时间', r'(随着|近年来|长期以来|当前|目前|传统上|自.{1,12}以来|在.{1,20}(背景|时代|过程)(下|中))'),
]
PROBLEM = r'(争议|争论|分歧|见解不一|看法不一|观点不一|莫衷一是|尚未|未能|存疑|困境|难题|挑战|模糊|不明|缺乏|空白|不足|滥用|混乱|质疑|误读|误解|疑问|是否|如何|何以|能否|问题)'
NORM = r'(应当|应|宜|须|需要|有必要|不得|可以|可|不宜|不应)'
OUTLOOK = r'(未来|将来|有待|前景|展望|今后|仍需|尚需|进一步完善|长远)'
SELF = r'(本文|笔者|作者|文章|本研究|拙文)'
ENUM = re.compile(r'[一-鿿]{2,10}、[一-鿿]{2,10}(?:、[一-鿿]{2,10})*(?:和|与|以及|及|或者|或)[一-鿿]{2,10}'
                  r'|[一-鿿]{2,10}(?:、[一-鿿]{2,10}){2,}')


def sents(t):
    return [s for s in re.findall(r'[^。！？]+[。！？]?', t) if len(s.strip()) > 1]


def cat(s):
    s = re.sub(r'^[“"‘《（(\s]+', '', s)
    for name, pat in CAT:
        if re.match(pat, s):
            return name
    return '无'


# ── 衔接 ─────────────────────────────────────────────────────────────
STOPW = set('我们 可以 应当 应该 不是 一个 以及 进行 具有 存在 认为 已经 没有 这种 这些 这一 这项 其中 通过 对于 关于 '
            '由于 因此 但是 而且 并且 同时 不同 相关 一定 主要 方面 问题 研究 分析 理论 本文 笔者 本人 他人 据此 然而 '
            '并不 只是 即使 如果 不仅 而是 就是 也是 之间 以上 以下 其他 所谓 可能 必须 需要 方可 作为'.split())
ANA = re.compile(r'^(这|该|此|其|上述|前述|如此|这样)')
TURN = re.compile(r'^(但是?|然而|不过|却)')
COND = re.compile(r'^(为了|为避免|唯有|只有|惟有)')
FRAME = re.compile(r'(有必要|更重要的是|关键在于|问题在于|核心在于|重心在于)')
COMMON = set()          # 语料里超过 15% 的摘要都用到的词（民法典、法律、规定……），不算接力


def words(s):
    return {w for w in jieba.cut(s) if len(w) >= 2 and re.fullmatch(r'[一-鿿]+', w) and w not in STOPW}


def link(s1, s2):
    """返回 (类型, 共同词)；类型为 head／later／none。"""
    w1 = words(s1) - COMMON
    head = [w for w in w1 if w in s2[:14]]
    if head:
        return 'head', head
    if ANA.match(s2):
        return 'head', ['（指代）' + ANA.match(s2).group()]
    shared = w1 & (words(s2) - COMMON)
    return ('later', sorted(shared)) if shared else ('none', [])


def analyse(t):
    S = sents(t)
    cats = [cat(s) for s in S]
    L = [link(a, b)[0] for a, b in zip(S, S[1:])]
    m = len(L) or 1
    prob = bool(re.search(PROBLEM, S[0])) or cats[0] == '背景时间'
    mid = S[1:3]
    return {
        'len': len(t), 'n': len(S), 'cats': cats,
        'conn': sum(c not in ('无', '背景时间') for c in cats) / len(S),
        'head': sum(x == 'head' for x in L) / m,
        'none': sum(x == 'none' for x in L) / m,
        'ana': any(ANA.match(s) for s in S[1:]),
        'prob': prob,
        'prob_bridge': {'句首转折': any(TURN.match(s) for s in mid), '句首指代': any(ANA.match(s) for s in mid),
                        '条件/目的句': any(COND.match(s) for s in mid), '改换提法': any(FRAME.search(s) for s in mid)},
        'self': bool(re.search(SELF, t)),
        'last_norm': bool(re.search(NORM, S[-1])),
        'outlook': bool(re.search(OUTLOOK, t)),
        'enum': len(ENUM.findall(t)),
    }


def q(v, p):
    v = sorted(v)
    return v[int(p * (len(v) - 1))]


def pctile(v, x):
    return round(100 * (sum(a < x for a in v) + 0.5 * sum(a == x for a in v)) / len(v))


def main():
    args = sys.argv[1:]
    opt = lambda k: args[args.index(k) + 1] if k in args else None
    root = args[0]
    exclude = tuple(x for x in (opt('--exclude') or '').split(',') if x)
    A = extract(root, exclude)
    if opt('--dump'):
        json.dump(A, open(opt('--dump'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    df = Counter()
    for a in A:
        df.update(words(a['abstract']))
    COMMON.update(w for w, c in df.items() if c / len(A) > 0.15)
    R = [dict(analyse(a['abstract']), author=a['author']) for a in A]
    n = len(R)
    by_au = defaultdict(list)
    for r in R:
        by_au[r['author']].append(r)

    print(f'摘要 {n} 篇 / {len(by_au)} 位作者（剔除通用词 {len(COMMON)} 个）\n')
    print('── 尺寸')
    for k, name in (('len', '字数（含标点）'), ('n', '句数')):
        v = [r[k] for r in R]
        print(f'  {name}：中位 {q(v, .5)}，Q1–Q3 {q(v, .25)}–{q(v, .75)}')
    print('── 句首连接语')
    allc = Counter(c for r in R for c in r['cats'])
    tot = sum(allc.values())
    print(f'  句首无连接语的句子：{allc["无"] / tot:.0%}；每篇有连接语的句子占比 中位 {q([r["conn"] for r in R], .5):.0%}，'
          f'Q3 {q([r["conn"] for r in R], .75):.0%}')
    for k in ('转折', '递进顺承', '因果推论', '让步', '承接问题', '条件', '总括'):
        users = sum(any(k in r['cats'] for r in rs) for rs in by_au.values())
        print(f'    {k}：{sum(k in r["cats"] for r in R) / n:.0%} 的摘要用过（{users}/{len(by_au)} 位作者）')
    print('── 衔接')
    for k, name in (('head', '后句开头接住前句（关键词或指代）'), ('none', '断开（无共同关键词）')):
        v = [r[k] for r in R]
        print(f'  {name}：每篇中位 {q(v, .5):.0%}，Q1–Q3 {q(v, .25):.0%}–{q(v, .75):.0%}')
    print(f'  用过指代起头（这一问题、这样的规定……）：{sum(r["ana"] for r in R) / n:.0%} 的摘要')
    print('── 结构')
    P = [r for r in R if r['prob']]
    print(f'  首句交代问题或背景：{len(P) / n:.0%}（{len(P)} 篇），其余多是开头直接下论断')
    if P:
        b = Counter(k for r in P for k, v in r['prob_bridge'].items() if v)
        anyb = sum(any(r['prob_bridge'].values()) for r in P)
        print(f'    其中第 2–3 句用了明确过渡的：{anyb / len(P):.0%}（' +
              '，'.join(f'{k} {b[k] / len(P):.0%}' for k in ('句首转折', '句首指代', '改换提法', '条件/目的句')) + '）')
    print(f'  末句是规范性主张（应、宜、须、可以…）：{sum(r["last_norm"] for r in R) / n:.0%}')
    print(f'  用到展望词（未来、有待、今后…）：{sum(r["outlook"] for r in R) / n:.0%}')
    print(f'  自指（本文、笔者、作者）：{sum(r["self"] for r in R) / n:.0%}')
    v = [r['enum'] for r in R]
    print(f'  ≥3 项并列：每篇中位 {q(v, .5)} 处，Q3 {q(v, .75)}')

    draft = opt('--text')
    if opt('--file'):
        m = re.search(r'^\**\s*(?:内容)?摘\s*要\s*\**\s*[:：]\s*\**(.+)$', open(opt('--file'), encoding='utf-8').read(), re.M)
        assert m, '稿件里找不到以「摘要：」开头的一行'
        draft = m.group(1).strip()
    if not draft:
        return
    d = analyse(draft)
    S = sents(draft)
    print(f'\n══ 待改稿摘要：{d["len"]} 字（P{pctile([r["len"] for r in R], d["len"])}），{d["n"]} 句'
          f'（P{pctile([r["n"] for r in R], d["n"])}）')
    print(f'  句首有连接语 {sum(c not in ("无", "背景时间") for c in d["cats"])}/{d["n"]}　'
          f'开头接住 {d["head"]:.0%}　断开 {d["none"]:.0%}　问题开头 {"是" if d["prob"] else "否"}　'
          f'末句规范性 {"是" if d["last_norm"] else "否"}　展望词 {"有" if d["outlook"] else "无"}　'
          f'自指 {"有 ⚠" if d["self"] else "无"}　并列≥3 {d["enum"]} 处')
    for i, (a, b) in enumerate(zip(S, S[1:]), 1):
        kind, ws = link(a, b)
        tag = {'head': '接住', 'later': '句中相关', 'none': '★断开'}[kind]
        c = cat(b)
        print(f'  {i}→{i + 1}　{tag}' + (f'：{"、".join(ws)}' if ws else '') + (f'　句首「{c}」' if c != '无' else ''))
    print('\n  逐处问：后一句为什么跟在前一句后面？★断开处先看能否删掉不承重的句子或调换顺序，'
          '再让后句开头接住前句的词；连接词最后考虑，一篇摘要一两处就够（第五节之二、第六节）。')


if __name__ == '__main__':
    main()
