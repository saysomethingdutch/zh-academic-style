# -*- coding: utf-8 -*-
"""因果核查：把稿子里每一处"强推断"拉出来，逐条交人核对。

用法：
  python3 scripts/causal_audit.py <稿件.md>              # 按类型列出全部强推断句（连同上一句）
  python3 scripts/causal_audit.py <稿件.md> --risky      # 只列高风险：涉及判例/立法者/学说却无注，或属排他、确认、等同类
  python3 scripts/causal_audit.py <旧稿.md> <新稿.md> --diff   # 只列新稿新增的强推断句（改写后必跑）

为什么要有它（2026-09，见 SKILL.md 第五节之三）：
  补句间逻辑时加进去的连接词，每一个都是一项承诺。实测一轮改写后，两个模型先后查出 30 处
  "新稿比旧稿多说了一层"，其中最严重的几处全是连接词造的：
    · 判例归因：「法院转而诉诸一般人格权益」——判决其实同时认定姓名权、肖像权与一般人格权受侵害
    · 判例归因：「替代的程度也确实影响了既有裁判的结果」——判决明示理由是原告未举证严重精神损害
    · 排他：「只有当保护的连接点落在……上，第1017条才顺理成章」——条文同样容得下另一种解释
    · 等同：「两者回答的是同一个问题」——识别"是谁"与认定"是其所为"并非同一问题
    · 条件越界：「认定只有在……交互中持续……时才会发生」——把"持续替代"的条件写成了"认定"的条件
  文风检测器全都测不到这些，它们只数词，不核对"这句话说的是不是真的"。

输出分七组，与 SKILL.md 第五节之三的表格同名：
  判例归因｜条件越界｜条文排他｜等同｜虚假理由｜确认语气｜一般推断
前六组一律算高风险；一般推断只在涉及判例、学说却未附注时算高风险。
回归测试：在"改坏的那一版"上，gpt-6-sol 查出的六处必须全部列出且归对组（当前 6/6）。

这个脚本不判断对错。它只保证每一处强推断都被一个人看过一眼。
"""
import re, sys

# 分组名与 SKILL.md 第五节之三的表格一一对应。顺序有讲究：先匹配的先归类，
# 所以「只有在……时才」（条件越界）必须排在「只有……才」（条文排他）之前。
TYPES = [
 ('判例归因', r'(法院|判决|裁判|法官|立法者|立法|条文|该条|该款|学说|论者|学者)[^。]{0,40}(之所以|是因为|原因在于|理由在于|因而|转而|最终|据此|正是|以此|出于)'),
 ('条件越界', r'(只有在[^。]{1,40}时才|须[^。]{1,30}才|以[^。]{1,20}为前提)'),
 ('条文排他', r'(只有[^。]{1,40}才|唯有|只能解释为|只能理解为|无从解释|无法解释|必然|必定|顺理成章|别无|不可能)'),
 ('等同',     r'(同一个问题|同一回事|并无二致|无异于|等同于|实质上就是|无非是)'),
 ('虚假理由', r'(之所以[^。]{0,40}是因为|正因为|正是因为|原因在于|理由在于|由于[^。]{0,30}[，,][^。]{0,30}(便|就|因而|所以|故))'),
 ('确认语气', r'(确实|的确(?!定)|正可|恰可|一一对应|已经在按|已经按|足以证明|足见|无疑|毫无疑问|显然)'),
 ('一般推断', r'(可见|由此可见|说明了?|表明|意味着|据此|由此|从而|因此|因而|故)'),
]
# 「一般推断」以外的六组一律视为高风险；「一般推断」只在涉及判例、学说却未附注时算高风险
RISKY = {'判例归因', '条件越界', '条文排他', '等同', '虚假理由', '确认语气'}
CITE = re.compile(r'〔(?:原注|新增)[^〕]*〕|\[\^\d+\]|（[^）]*第\d+条[^）]*）')
# 「案」须排除 个案、方案、草案、议案、预案、提案、档案、答案 等非判例用法
CASEWORD = re.compile(r'((?<![个方草议预提档答])案|判决|法院|裁判|学说|论者|学者|报告|立法者)')

def body(path):
    t = open(path, encoding='utf-8').read()
    t = t.split('<!-- 以下')[0]
    i = t.find('## 一、'); t = t[i:] if i >= 0 else t
    paras = [p.strip() for p in t.split('\n\n')
             if p.strip() and not p.lstrip().startswith(('#', '|', '表', '**', '[^'))]
    out = []
    for p in paras:
        ss = [s.strip() for s in re.split(r'(?<=[。？！])', p) if len(re.findall(r'[一-鿿]', s)) > 4]
        for k, s in enumerate(ss):
            out.append((ss[k-1] if k else '（段首）', s))
    return out

def classify(s):
    hits = []
    for name, pat in TYPES:
        m = re.search(pat, s)
        if m: hits.append((name, m.group(0)))
    return hits

def risky(name, s):
    if name in RISKY: return True
    return bool(CASEWORD.search(s) and not CITE.search(s))

def audit(path, only_risky=False, skip=None):
    rows = []
    for prev, s in body(path):
        if skip and s in skip: continue
        for name, w in classify(s):
            if only_risky and not risky(name, s): continue
            rows.append((name, w, prev, s)); break
    return rows

def show(rows):
    order = [t[0] for t in TYPES]
    for name in order:
        rs = [r for r in rows if r[0] == name]
        if not rs: continue
        print(f'\n══ {name}（{len(rs)} 处）')
        for _, w, prev, s in rs:
            print(f'  ▸【{w}】{s[:150]}{"…" if len(s) > 150 else ""}')
            print(f'     上一句：{prev[:90]}{"…" if len(prev) > 90 else ""}')
    print(f'\n共 {len(rows)} 处。逐条问：这一层推断的依据在哪里？判例归因须与判决的明示理由一致；'
          f'条文推理写「更宜理解为」而非「可见」「只有」；排他须点名并排除竞争解释；'
          f'等同须写出两边各回答什么；条件须核对它限定的是哪个概念。')

def main():
    a = [x for x in sys.argv[1:] if not x.startswith('--')]
    if not a: print(__doc__); sys.exit(1)
    if '--diff' in sys.argv and len(a) >= 2:
        old = {s for _, s in body(a[0])}
        rows = audit(a[1], only_risky='--risky' in sys.argv, skip=old)
        print(f'新稿新增的强推断句（旧稿中不存在的句子）：')
    else:
        rows = audit(a[0], only_risky='--risky' in sys.argv)
    show(rows)

if __name__ == '__main__':
    main()
