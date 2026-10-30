#!/usr/bin/env python3
"""rebuttal_stats: 商榷（反驳）的频率与写法——中文法学论文怎样回应他人观点。

两件事分开测：
1. 有没有反驳、有多少：引述他人观点（有学者认为/有观点认为/这一观点/X说……）之后三句内
   出现不同意的标记（但/然而/笔者认为/值得商榷/存在……障碍/理由并不充分……）记一处。
   这是粗筛：抽检约三分之二是真反驳，其余是“正如有学者指出……但”之类的赞同引用。
   报告里的比例要读成“上限”，结论靠 --list 逐条读。
2. 怎么指称被反驳的观点：中文论文用“有学者认为”“这一观点”“该说”，当场引、当场驳；
   给对方观点起名后隔节回指（“否定论证的第二项理由”“前述X研究”“以Y为要件的意见”）
   在知产所 321 篇里 0 次——这是从英文论文搬来的结构。

usage:
  rebuttal_stats.py corpus <语料目录> [--qual 正则]   # 基准；--qual 按题目分出定性类论文（默认：属性|性质|定性|可版权性|可专利性|构成|认定|客体|界定）
  rebuttal_stats.py draft <稿.md> [--list]            # 稿件：反驳处数、/万字、自造标签回指
"""
import re, sys, glob, statistics as st
from pathlib import Path

CITE = re.compile(r'((有|也有|另有|还有|诸多|部分)学者(认为|指出|主张|提出|担心|将)|(已有|也有|另有)研究(认为|指出|多持)|有观点|有论者|另一种观点|'
                  r'(这一|该|上述|此种|这种|此)(观点|见解|主张|看法|学说)|[^。，]{1,8}说认为)')
NEG = re.compile(r'(但(是)?[，,]?|然而|不过|笔者认为|笔者并不|本文认为|值得商榷|有待商榷|'
                 r'(存在|有)[^。]{0,8}(瑕疵|缺陷|障碍|问题|不足)|混淆|忽视|忽略|难以成立|不能成立|'
                 r'并不(妥当|充分|准确|合理)|理由并不|难以(适用|解释|成立)|失之|不妥|不可取|'
                 r'(并未|没有)将其规定为|不能用来证明|不宜设为|与[^。]{1,12}无关|只是对[^。]{1,12}的描述|是对[^。]{1,12}的描述)')
AGREE = re.compile(r'^(正如|笔者(也)?赞同|本文(赞同|认可|采))')
# 自造标签：给被反驳的观点起名后回指（语料 0 次）
LABEL = re.compile(r'(否定论证|肯定论证|否定(观点|意见)的第[一二三四五]|第[一二三四五]项理由|'
                   r'前述[^，。]{1,10}(研究|论证)(认为|指出|所说|的)|以[^，。]{1,10}为要件的意见)')
QUAL = r'(属性|性质|定性|可版权性|可专利性|构成|认定|客体|界定)'
CJK = re.compile(r'[一-鿿]')


def body_of(path):
    t = Path(path).read_text(encoding='utf-8', errors='ignore')
    t = re.split(r'\n#+\s*(参考文献|注释|注\s*释)\s*\n', t)[0]
    t = '\n'.join(l for l in t.split('\n') if not re.match(r'^\[\^\w+\]:', l))
    return re.sub(r'\$[^$]*\$|\[\^?\d+\]', '', t)


def scan(text):
    S = [s for s in re.split(r'(?<=[。！？])', text) if s.strip()]
    cites, hits = 0, []
    for i, s in enumerate(S):
        if CITE.search(s):
            cites += 1
            win = ''.join(S[i:i + 3])
            if NEG.search(win[len(s) // 2:]) and not AGREE.search(s):
                hits.append(win)
    return cites, hits


def q(L):
    L = sorted(L); k = len(L)
    return (L[k // 4], st.median(L), L[3 * k // 4]) if k else (0, 0, 0)


def corpus(d, qual):
    R = []
    for f in sorted(glob.glob(str(Path(d) / '*.md'))):
        b = body_of(f); n = len(CJK.findall(b))
        if n < 6000:
            continue
        c, h = scan(b)
        R.append(dict(f=Path(f).stem, n=n, c=c, r=len(h), lab=len(LABEL.findall(b)),
                      qual=bool(re.search(qual, Path(f).stem.split('_')[0]))))

    def rep(name, L):
        if not L:
            return
        has = sum(1 for r in L if r['r'])
        print(f"{name}: n={len(L)}  有反驳的篇数 {has} ({has / len(L) * 100:.0f}%，上限)  "
              f"每篇反驳 Q1/中位/Q3 {q([r['r'] for r in L])}  /万字 Q3 {q([r['r'] / r['n'] * 1e4 for r in L])[2]:.1f}  "
              f"引述后表示不同意 {sum(r['r'] for r in L) / max(1, sum(r['c'] for r in L)) * 100:.0f}%  "
              f"自造标签回指 {sum(r['lab'] for r in L)} 次")
    rep('全部', R)
    rep('定性/认定类', [r for r in R if r['qual']])
    rep('其他', [r for r in R if not r['qual']])


def draft(path, show):
    b = body_of(path); n = len(CJK.findall(b))
    c, h = scan(b)
    labs = LABEL.findall(b)
    print(f"{Path(path).name}: 汉字={n}  引述他人观点={c}  反驳处={len(h)}  /万字={len(h) / n * 1e4:.1f}  "
          f"自造标签回指={len(labs)}（语料 0）")
    if labs:
        print('  标签：', sorted(set(m[0] for m in labs)))
    if show:
        for w in h:
            print('  ▸', w.replace('\n', '')[:200])


if __name__ == '__main__':
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    if sys.argv[1] == 'corpus':
        qual = sys.argv[sys.argv.index('--qual') + 1] if '--qual' in sys.argv else QUAL
        corpus(sys.argv[2], qual)
    else:
        draft(sys.argv[2], '--list' in sys.argv)
