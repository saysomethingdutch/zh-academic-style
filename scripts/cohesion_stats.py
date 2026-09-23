# -*- coding: utf-8 -*-
"""句间逻辑连接的测量——查「每句都像 bullet point」。

用法：
  python3 scripts/cohesion_stats.py <语料目录> <稿件.md> [更多稿件…]

三个指标，全部按「整句」（到。？！）计：
  ① 句首连接词占比：句首 8 字内出现因果/转折/条件/递进/解释/让步类连接词的句子比例
  ② 句内因果链占比：句中含 因为/由于/所以/因此/从而/既然/之所以/则/便/就/于是 等的句子比例
  ③ 段首承接上段占比：段首句以连接词或回指词（这/此/该/上述/前述/前例/同理…）起头的段落比例

2026-09 实测（民法所 386 篇，Q1/中位/Q3）：
  ① 17.1 / 21.7 / 27.4　（其中因果 7.4、转折 4.6、条件 3.2）
  ② 30.2 / 36.3 / 43.4
  ③ 11.2 / 17.8 / 25.0
一份 AI 协作稿：① 4.9%（P4），转折 0.6%（P1）——每二十句才有一句交代自己与上一句的关系。
见 SKILL.md 第五节之二。
"""
import re, sys, os, glob, bisect, statistics as st
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mineru_body import body_paras

HEAD = {
 '因果': r'(因此|因而|所以|故而|是故|于是|由此|可见|据此|从而|正因|既然|由于|因为|这样一来|如此一来|结果是|故)',
 '转折': r'(但是|但|然而|不过|可是|反之|相反|却|只是)',
 '条件': r'(如果|倘若|假如|若|一旦|只有|只要|否则|除非|无论|不论)',
 '递进': r'(而且|并且|况且|何况|甚至|进而|更何况|不仅|此外|另外|同时|再者)',
 '解释': r'(换言之|也就是说|亦即|具体而言|具体来说|例如|比如|譬如|质言之|事实上|实际上)',
 '让步': r'(虽然|尽管|即便|即使|固然|纵然)',
}
INNER = r'(因为|由于|所以|因此|因而|从而|以致|既然|之所以|才|否则|则|便|就|于是)'
BACKREF = r'(这|此|该|上述|前述|如前|据此|前文|前例|同理|同样|与此)'

def sents(t):
    return [s for s in re.split(r'(?<=[。？！])', t) if len(re.findall(r'[一-鿿]', s)) > 4]

def _head(s, n=8):
    return re.sub(r'^[“”"（(〔\s]*', '', s)[:n]

def analyse(paras):
    S = [s for p in paras for s in sents(p)]
    n = len(S) or 1
    cnt = {k: 0 for k in HEAD}; anyhead = inner = 0
    for s in S:
        h = _head(s)
        for k, pat in HEAD.items():
            if re.match(r'^.{0,3}' + pat, h):
                cnt[k] += 1; anyhead += 1; break
        if re.search(INNER, s): inner += 1
    link = 0
    for p in paras[1:]:
        ss = sents(p)
        if ss and re.match(r'^.{0,3}(' + '|'.join(HEAD.values()) + '|' + BACKREF + ')', _head(ss[0], 10)):
            link += 1
    r = dict(n=n, head=anyhead/n*100, inner=inner/n*100, plink=link/max(len(paras)-1, 1)*100)
    r.update({k: v/n*100 for k, v in cnt.items()})
    return r

def draft_paras(path):
    t = open(path, encoding='utf-8').read()
    i = t.find('## 一、')
    t = t[i:] if i >= 0 else t
    t = t.split('<!-- 以下')[0]
    return [p.strip() for p in t.split('\n\n')
            if p.strip() and not p.lstrip().startswith(('#', '|', '表', '**', '[^'))]

ROWS = [('head', '① 句首有连接词 %'), ('因果', '   其中因果 %'), ('转折', '   其中转折 %'),
        ('条件', '   其中条件 %'), ('inner', '② 句内有因果链 %'), ('plink', '③ 段首承接上段 %')]

def main():
    if len(sys.argv) < 3:
        print(__doc__); sys.exit(1)
    root, drafts = sys.argv[1], sys.argv[2:]
    R = []
    for f in sorted(glob.glob(os.path.join(root, '**', '*.md'), recursive=True)):
        ps = body_paras(f)
        if len(ps) < 15 or len(re.findall(r'[一-鿿]', ''.join(ps))) < 3000: continue
        R.append(analyse(ps))
    print(f'语料 {len(R)} 篇（Q1 / 中位 / Q3）')
    for k, nm in ROWS:
        v = sorted(r[k] for r in R); m = len(v)
        print(f'  {nm:18} {v[m//4]:5.1f} / {st.median(v):5.1f} / {v[3*m//4]:5.1f}')
    for d in drafts:
        r = analyse(draft_paras(d))
        print(f'\n{os.path.basename(d)}（{r["n"]} 句）')
        for k, nm in ROWS:
            v = sorted(x[k] for x in R); pct = bisect.bisect(v, r[k]) / len(v) * 100
            flag = '  ⚠<Q1' if r[k] < v[len(v)//4] else ''
            print(f'  {nm:18} {r[k]:5.1f}   P{pct:.0f}{flag}')

if __name__ == '__main__':
    main()
