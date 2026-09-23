# -*- coding: utf-8 -*-
"""从 MinerU 解析出的 markdown 中抽取**正文自然段**。

MinerU 的 md 已经给出正确的段落边界与标题分级，质量远高于坐标启发式，
因此这里不再需要 MIN_PARA=60 那种挡碎片的补丁（阈值降到 25 即可）。

要剔除的非正文：DOI 行、标题、作者与单位、中英文摘要与关键词、
中图分类号/文献标识码/文章编号、参考文献与注释区、图表标记、
以及页眉页脚残留。
"""
import re, os, glob

MIN_PARA = 25

# 正文结束标志（出现即截断其后全部内容）
END_HEADS = re.compile(
    r'^#{1,4}\s*[\[【]?\s*(参考文献|注释|注\s*释|references?|参考资料|引注|附录)\s*[\]】]?\s*[:：]?\s*$',
    re.I)
# 非正文行（整行丢弃）
DROP_LINE = re.compile(
    r'^(DOI|doi)\s*[:：]|'
    r'^(摘\s*要|关键词|关 键 词|中图分类号|文献标识码|文章编号|收稿日期|基金项目|作者简介|Abstract|Key\s*words?)\s*[:：]|'
    r'^[（(].{0,60}(大学|学院|研究所|研究院|中心)[^)）]{0,30}[)）]\s*$|'   # 单位行
    r'^!\[|^<html|^</?table|^\|', re.I)
# 漏网的引注/列表/表格残留（MinerU 也不能完全隔离），整行丢弃
DROP2 = re.compile(
    r'^[\[［]\s*\d{1,3}\s*[\]］]|'          # [19] 参考文献条目
    r'^(参见|另见|转引自|See\s|Cf\.)|'          # 脚注体例
    r'^\d{1,2}\s*[.、)）]\s*|'                 # "5. …" 列表项
    r'^[—–\-•·]|'                             # 破折号/项目符号起首的子项
    r'^[a-zA-Z]{1,3}\s*[.)）]\s*', re.I)

def clean(s: str) -> str:
    s = re.sub(r'[​-‏﻿　]', '', s)
    s = re.sub(r'\$\^?\{?[①-⑳\d,\s]{1,12}\}?\$', '', s)      # $^{①}$ 之类的注号
    s = re.sub(r'[①-⑳]', '', s)                              # 行内注号
    s = re.sub(r'\[\^[^\]]+\]', '', s)
    s = re.sub(r'\s+', '', s) if False else s
    return s.strip()

def cjk_ratio(s): return len(re.findall(r'[一-鿿]', s)) / max(len(s), 1)

def body_paras(path):
    raw = open(path, encoding='utf-8', errors='ignore').read()
    out, started = [], False
    for line in raw.split('\n'):
        t = line.strip()
        if not t:
            continue
        if END_HEADS.match(t):
            break
        if t.startswith('#'):
            started = True          # 第一个标题之后才算正文区
            continue
        if not started:
            continue
        if DROP_LINE.match(t) or DROP2.match(t):
            continue
        p = clean(t)
        if len(p) < MIN_PARA:
            continue
        if cjk_ratio(p) < 0.5:      # 英文摘要、参考文献残留
            continue
        out.append(p)
    return out

def in_tmp(f, root):
    """f 是否位于 root 之下某个名为 tmp 的子目录里（任意层级）。

    只看 f 相对 root 的路径，不看绝对路径：旧写法 `'/tmp/' in f` 在语料目录本身
    位于 /tmp 或 /private/tmp 之下时（如会话 scratchpad 里建的软链目录）
    会把全部文件滤掉，下游随即除零。
    """
    return 'tmp' in os.path.relpath(f, root).split(os.sep)[:-1]

def expand(paths):
    """目录展开为其下全部 .md（跳过其中名为 tmp 的子目录）；文件与通配式原样取用。"""
    fs = []
    for a in paths:
        if os.path.isdir(a):
            fs += [f for f in sorted(glob.glob(os.path.join(a, '**', '*.md'), recursive=True))
                   if not in_tmp(f, a)]
        else:
            fs += sorted(glob.glob(a))
    return fs
