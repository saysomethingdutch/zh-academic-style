#!/usr/bin/env python3
"""attrib_stats: 正文点名被引学者的频率（"某某指出/认为……"），以及脚注写法。

口径：从脚注/文末注释里抽出被引中文作者名（"作者：《" 或 "作者、作者：《"），
再在正文里找"作者名 +（也/亦/则/曾）+ 指出|认为|主张|强调|提出|注意到|批评|探讨|讨论|梳理|分析|转述"。
外国学者另用 --foreign 名单（中文译名，逗号分隔）。机构主体（专家组、上诉机构、发言人）不计。

usage:
  attrib_stats.py corpus DIR            # 语料：*.md，脚注附在文末（MinerU page_footnote 附录或 [^n]: 行）
  attrib_stats.py draft FILE.md [--foreign 阿德隆,秦,希思]   # 稿件：[^n]: 脚注行
"""
import re, sys, glob, statistics as st

VERBS = r'(指出|认为|主张|强调|提出|注意到|发现|论证|批评|质疑|揭示|概括|总结|分析|探讨|讨论|梳理|转述)'
STOP = {'参见', '载于', '转引', '引自', '例如', '同上', '参考', '另参见', '本文', '笔者'}
CJK = re.compile(r'[一-鿿]')


def split(t):
    k = max(t.rfind('页脚注'), t.rfind('## 脚注'), t.rfind('page_footnote'))
    if k > len(t) * 0.5:
        return t[:k], t[k:]
    lines = t.split('\n')
    fn = '\n'.join(l for l in lines if re.match(r'^\[\^\w+\]:', l))
    body = '\n'.join(l for l in lines if not re.match(r'^\[\^\w+\]:', l))
    return body, fn


def authors_in(fn):
    a = set()
    for m in re.finditer(r'([一-鿿]{2,3}(?:、[一-鿿]{2,3})*)(?:等)?[：:]\s*[《“]', fn):
        a |= set(m.group(1).split('、'))
    return a - STOP


def named(body, names):
    n = 0
    for a in names:
        n += len(re.findall(re.escape(a) + r'(?:教授|等|等人)?(?:也|亦|则|曾|进一步|明确)?' + VERBS, body))
    return n


def fn_style(fn):
    L = [re.sub(r'^\s*(?:\[\^\w+\]:|[\-\*]?\s*[\[\(（]?[①-⑳\d]+[\]\)）]?)\s*', '', l.strip()) for l in fn.split('\n') if '《' in l or 'See ' in l]
    L = [l for l in L if 10 < len(l) < 400]
    if not L:
        return {}
    c = lambda p: round(100 * sum(1 for l in L if re.search(p, l)) / len(L))
    return {'脚注行': len(L), '参见开头%': c(r'^参见'), '具体页码%': c(r'第\d+(?:[—\-–]\d+)?页|pp?\. ?\d'),
            '一注多文献%': c(r'页；|；参见|；See')}


def main():
    mode = sys.argv[1]
    if mode == 'corpus':
        R, G, S = [], [], []
        for f in glob.glob(sys.argv[2].rstrip('/') + '/*.md'):
            t = open(f, encoding='utf-8', errors='ignore').read()
            body, fn = split(t)
            names = authors_in(fn)
            n = len(CJK.findall(body))
            if n < 6000 or len(names) < 4:
                continue
            R.append(named(body, names) / n * 1e4)
            G.append(len(re.findall(r'(有学者|也有学者|还有学者|另有学者|有观点认为|有论者)', body)) / n * 1e4)
            S.append(fn)
        q = lambda L: (round(sorted(L)[len(L) // 4], 1), round(st.median(L), 1), round(sorted(L)[3 * len(L) // 4], 1))
        print(f'n={len(R)}  点名/万字 Q1/中位/Q3={q(R)}  "有学者"/万字={q(G)}')
        print('脚注写法', fn_style('\n'.join(S)))
    else:
        t = open(sys.argv[2], encoding='utf-8').read()
        body, fn = split(t)
        names = authors_in(fn)
        if '--foreign' in sys.argv:
            names |= set(sys.argv[sys.argv.index('--foreign') + 1].split(','))
        n = len(CJK.findall(body))
        k = named(body, names)
        print(f'{sys.argv[2]}: 汉字={n} 点名={k} 每万字={k / n * 1e4:.1f}  "有学者"={len(re.findall("有学者", body))}')
        print('脚注写法', fn_style(fn))


if __name__ == '__main__':
    main()
