#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""中文学术文风量化统计器。

用法：
    python3 style_stats.py <文件或目录> [<文件或目录> ...] [--json]

支持 .md / .txt / .pdf / .docx。对每份文档输出：
  段首句类型分布、元话语率、序号词占比、顿号密度、句长分布、
  自造范畴词复现、破折号与冒号频次。

设计原则：只测量，不判断。阈值交给人（见 SKILL.md 的判定纪律）——
密度类指标很容易骗人，本脚本刻意不输出"合格/不合格"。
"""
import re, sys, json, glob, os, statistics as st
from collections import Counter

# ── 文本清洗 ──────────────────────────────────────────────
ZERO_WIDTH = '[​-‏﻿ 　]'

def norm(s: str) -> str:
    """去零宽/全角空格，并消除 PDF 提取常见的中文字间空格。"""
    s = re.sub(ZERO_WIDTH, '', s)
    for _ in range(4):
        s = re.sub(r'([一-鿿，。；：、“”（）《》？！])\s+'
                   r'([一-鿿，。；：、“”（）《》？！])', r'\1\2', s)
    return s.strip()

def cjk_ratio(s: str) -> float:
    return len(re.findall(r'[一-鿿]', s)) / max(len(s), 1)

# ── 段落提取：三种来源 ────────────────────────────────────
def paras_from_pdf(path):
    """PDF 用首行缩进判段。中文论文首行缩进两字符，比行宽可靠得多。

    退化处理：某些 PDF 文本流碎片化（每个标点单独成行），行宽法完全失效，
    但缩进法仍然有效，因为它依据坐标而非换行。
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        sys.exit("需要 PyMuPDF：pip install pymupdf")
    doc = fitz.open(path)
    lines = []
    for pg in doc:
        for blk in pg.get_text("dict").get("blocks", []):
            for ln in blk.get("lines", []):
                txt = norm("".join(sp["text"] for sp in ln.get("spans", [])))
                if not txt:
                    continue
                size = max((sp["size"] for sp in ln.get("spans", [])), default=0)
                lines.append((round(ln["bbox"][0], 1), txt, round(size, 1)))
    if not lines:
        return []
    # 正文字号 = 中文长行里出现最多的字号（脚注、页眉字号更小）
    cand = [sz for _, t, sz in lines if cjk_ratio(t) > 0.5 and len(t) > 10]
    if not cand:
        return []
    body_size = Counter(cand).most_common(1)[0][0]
    body = [(x, t) for x, t, sz in lines
            if abs(sz - body_size) < 0.6 and cjk_ratio(t) > 0.35 and len(t) > 4]
    if not body:
        return []
    left = Counter(x for x, _ in body).most_common(1)[0][0]
    out, buf = [], ""
    for x, t in body:
        if re.match(r'^[·\[]?\d+[·\]]?$', t) or t[0] in '①②③④⑤⑥⑦⑧⑨⑩':
            continue
        if x > left + 8 and buf:          # 首行缩进 → 新段
            if len(buf) > 60:
                out.append(buf)
            buf = t
        else:
            buf += t
    if len(buf) > 60:
        out.append(buf)
    return out

def paras_from_text(path):
    if path.lower().endswith('.docx'):
        try:
            from docx import Document
        except ImportError:
            sys.exit("需要 python-docx：pip install python-docx")
        raw = "\n".join(p.text for p in Document(path).paragraphs)
    else:
        raw = open(path, encoding='utf-8', errors='ignore').read()
    out = []
    for line in raw.split('\n'):
        s = line.strip()
        # 脚注/参考文献定义必须先判断：若先删标记，"[^98]: 张凌寒…" 会变成
        # ": 张凌寒…"，此后再也识别不出，整段被当成正文（实测污染 100 条脚注）。
        if re.match(r'^\[\^', s) or re.match(r'^\[\d+\]\s', s):
            continue
        p = norm(re.sub(r'\[\^[^\]]+\]', '', s))       # 去正文中的脚注引用
        if len(p) < 60 or p.startswith(('#', '|', '>', '!', '```', ':', '：')):
            continue
        out.append(p)
    return out

def load(path):
    if path.lower().endswith('.pdf'):
        return paras_from_pdf(path)
    return paras_from_text(path)

# ── 段首句分类 ────────────────────────────────────────────
PAT_ORDINAL = (r'^(第[一二三四五六七八九十]+[，,、]|首先|其次|再次|最后|'
               r'一方面|另一方面|其[一二三四五六七八九]|[（(][一二三四五六七八九1-9][)）])')
PAT_CONNECT = (r'^(由此可见|综上|可见|因此|据此|故|从这个意义|正是基于此|此外|同时|'
               r'与之|相较于|和.{1,12}相比|上述|如前所述|可以预见|在此基础上)')
PAT_ADVERB  = r'^(从|在|就|依|按|随着|面对|针对|围绕|基于|作为|鉴于|若|如果|一旦|当)'
PAT_CONCEDE = r'^(尽管|虽然|但|然而|不过|有(观点|学者|研究)|亦有|诸多|论者)'
# 元话语：**零信息量**的纯结构预告或写作播报。
# 判据：这句话单独拎出来，能否作为一个论断被引用？不能，才是元话语。
#   「但该理论主要有三个不足。」→ 能（"该理论有不足"是实质判断）→ 不是元话语
#   「德国法通过两则判例确立了X。」→ 能 → 不是元话语
#   「论证可分三步。」→ 不能（离开上下文无意义）→ 是元话语
# 实测：李昶（清华法学）、范晓波都使用带实质判断的段首中心句，含"问题在于""本文主张"，
# 故此类一律不判为元话语。只抓真正的空壳句。
PAT_META = (r'^(论证|检验|分析|讨论|说明|理由|以下|下文)?(可)?分(为)?[一二三四五六七八九十\d]+[步点类个]?[。：，]|'
            r'^.{0,12}(可以)?用一句话(概括|说明|表述)|'
            r'^(以|用|举)一(个|则)?(假想)?(案例|例子|示例)(来)?(演示|说明|检验)|'
            r'^(接下来|下面|以下)(将|要|我们)?(讨论|分析|说明|论述|展开)|'
            r'^.{0,14}(须|应|需|要)先(理解|厘清|界定|说明|讨论|回答)|'
            r'^.{0,16}(应|须|可)从[一二三四五六七八九十\d]+个?(方面|层面|角度|步骤)展开[：:。]|'
            r'^(本文|本部分|本节)(的)?(主张|观点|结论|思路|安排|结构)(可以|是|如下)[：:]|'
            r'^.{0,10}的内容已见.{0,12}[，,]此处(只|仅)|'
            r'^(前文|上文)(已)?(处理|讨论|论述)的?(都)?是')

def classify(s):
    if re.match(PAT_ORDINAL, s): return '序号并列'
    if re.match(PAT_CONNECT, s): return '承接推论'
    if re.match(PAT_META, s):    return '元话语'      # 先于状语，"在展开分析前"属元话语
    if re.match(PAT_ADVERB, s):  return '状语引导'
    if re.match(PAT_CONCEDE, s): return '让步对话'
    return '实体陈述'

def first_sentence(p):
    m = re.match(r'^(.{1,60}?[。；：？])', p)
    return m.group(1) if m else p[:50]

# ── 统计主体 ──────────────────────────────────────────────
def analyse(paras, name=""):
    firsts = [first_sentence(p) for p in paras]
    kinds = Counter(classify(s) for s in firsts)
    n = max(len(firsts), 1)
    sents = [s for p in paras for s in re.split(r'(?<=[。；？])', p) if len(s) > 15]
    ns = max(len(sents), 1)
    lens = [len(s) for s in sents]
    full = "\n".join(paras)

    # 顿号罗列
    e4 = sum(1 for s in sents if s.count('、') >= 4)
    e3 = sum(1 for s in sents if s.count('、') >= 3)
    runs = re.findall(r'[一-鿿]{2,6}(?:、[一-鿿]{2,6}){2,}', full)
    # 罗列成分的词频：同一批词反复重组＝报菜名的真正来源
    items = [w for r in runs for w in r.split('、')]
    repeat = [(w, c) for w, c in Counter(items).most_common(12) if c >= 3]

    return {
        "文件": name,
        "段数": len(firsts),
        "句数": len(sents),
        "元话语率%": round(kinds['元话语'] / n * 100, 1),
        "序号词%": round(kinds['序号并列'] / n * 100, 1),
        "实体陈述%": round(kinds['实体陈述'] / n * 100, 1),
        "承接%": round(kinds['承接推论'] / n * 100, 1),
        "状语%": round(kinds['状语引导'] / n * 100, 1),
        "让步%": round(kinds['让步对话'] / n * 100, 1),
        "顿号≥4句%": round(e4 / ns * 100, 1),
        "顿号≥3句%": round(e3 / ns * 100, 1),
        "顿号串数": len(runs),
        "高频罗列词": repeat,
        "句长中位": round(st.median(lens)) if lens else 0,
        "句长均值": round(st.mean(lens)) if lens else 0,
        "短句<35字%": round(sum(1 for x in lens if x < 35) / max(len(lens),1) * 100),
        "破折号/段": round(full.count('——') / n, 2),
        "_元话语句": [s for s in firsts if classify(s) == '元话语'],
    }

def expand(args):
    out = []
    for a in args:
        if os.path.isdir(a):
            for ext in ('*.pdf', '*.md', '*.txt', '*.docx'):
                out += sorted(glob.glob(os.path.join(a, ext)))
        else:
            out += sorted(glob.glob(a))
    return out

def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    as_json = '--json' in sys.argv
    if not args:
        sys.exit(__doc__)
    results = []
    for f in expand(args):
        try:
            ps = load(f)
        except Exception as e:
            print(f"  [跳过] {os.path.basename(f)[:44]} — {e}", file=sys.stderr)
            continue
        if len(ps) < 10:
            print(f"  [段落不足 {len(ps)}，跳过] {os.path.basename(f)[:44]}", file=sys.stderr)
            continue
        results.append(analyse(ps, os.path.basename(f)))

    if as_json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return
    if not results:
        sys.exit("没有可分析的文档。")

    hdr = f"{'文件':<34}{'段':>4}{'元话语%':>8}{'序号%':>7}{'实体%':>7}{'顿≥4%':>7}{'顿≥3%':>7}{'句长':>6}{'破折/段':>8}"
    print(hdr); print("-" * len(hdr))
    for r in results:
        print(f"{r['文件'][:33]:<34}{r['段数']:>4}{r['元话语率%']:>8}{r['序号词%']:>7}"
              f"{r['实体陈述%']:>7}{r['顿号≥4句%']:>7}{r['顿号≥3句%']:>7}{r['句长中位']:>6}{r['破折号/段']:>8}")
    if len(results) > 1:
        print("-" * len(hdr))
        for k in ['元话语率%','序号词%','实体陈述%','顿号≥4句%','顿号≥3句%','句长中位']:
            v = [r[k] for r in results]
            print(f"  {k:<10} 均值 {st.mean(v):>6.1f}   范围 {min(v):>5.1f} – {max(v):>5.1f}")

    for r in results:
        if r['_元话语句'] or r['高频罗列词']:
            print(f"\n── {r['文件'][:50]}")
        if r['_元话语句']:
            print("   元话语式段首：")
            for s in r['_元话语句'][:12]:
                print(f"     · {s[:56]}")
        if r['高频罗列词']:
            print("   高频罗列成分（同一批词反复重组＝报菜名）：")
            print("     " + "，".join(f"{w}×{c}" for w, c in r['高频罗列词']))

if __name__ == '__main__':
    main()
