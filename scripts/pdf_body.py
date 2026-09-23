# -*- coding: utf-8 -*-
"""按**字号**从 PDF 抽正文、剔脚注——建语料的第三条路（需要 PyMuPDF）。

    python3 scripts/pdf_body.py <PDF目录或文件…> -o <输出目录>

MinerU 解析质量最好但要跑 API；`paras_pdf()` 的首行缩进启发式质量最低。
这条路介于两者之间，且**不联网、秒级完成**：中文期刊的脚注字号一定小于正文，
逐篇取"汉字数最多的那个字号"为正文字号，只保留 >= 该字号-0.6 的文本行。

**跑完必须做污染自查**（脚注混进来会毁掉所有密度指标）：

    cat <输出目录>/*.txt | grep -o -E "参见|载《|期，第|转引自" | sort | uniq -c

干净的语料这一条应当**接近 0**。不为 0 就说明字号阈值没切干净，
调 -0.6 这个容差或改用 MinerU。

**限制**：只重建"哪些字属于正文"，不重建段落边界（PDF 行 ≠ 自然段）。
所以它适合测**词频与密度**（每万字多少次），**不适合测句长、段长、CV**——
那些必须用 MinerU 或 `paras_pdf()`。
"""
import re, os, sys, glob
from collections import Counter

def body_text(path, tol=0.6):
    import fitz
    doc = fitz.open(path)
    sizes = Counter()
    for p in doc:
        for b in p.get_text("dict")["blocks"]:
            for l in b.get("lines", []):
                for s in l.get("spans", []):
                    n = len(re.findall(r'[一-鿿]', s["text"]))
                    if n: sizes[round(s["size"], 1)] += n
    if not sizes: return None, None
    body = sizes.most_common(1)[0][0]
    out = []
    for p in doc:
        for b in p.get_text("dict")["blocks"]:
            for l in b.get("lines", []):
                txt = "".join(s["text"] for s in l.get("spans", []) if s["size"] >= body - tol)
                if txt.strip(): out.append(txt.strip())
    return "\n".join(out), body

def main():
    args = [a for a in sys.argv[1:] if a != '-o']
    if '-o' not in sys.argv or len(args) < 2:
        print(__doc__); sys.exit(1)
    out = args[-1]; srcs = args[:-1]
    os.makedirs(out, exist_ok=True)
    fs = []
    for s in srcs:
        fs += sorted(glob.glob(os.path.join(s, "*.pdf"))) if os.path.isdir(s) else sorted(glob.glob(s))
    for f in fs:
        t, size = body_text(f)
        if t is None:
            print(f"跳过（无中文）：{os.path.basename(f)}"); continue
        name = os.path.splitext(os.path.basename(f))[0]
        open(os.path.join(out, name + ".txt"), "w", encoding="utf-8").write(t)
        print(f"{name[:40]:42s} 正文字号={size} 汉字={len(re.findall(r'[一-鿿]', t))}")
    print(f"\n→ {out}\n务必做污染自查：")
    print(f'  cat {out}/*.txt | grep -o -E "参见|载《|期，第|转引自" | sort | uniq -c   # 应接近 0')

if __name__ == '__main__':
    main()
