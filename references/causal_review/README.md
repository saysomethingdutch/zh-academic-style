# 第二模型因果核查（固定清单第 ⑧ 条之二）

改写（尤其是补句间逻辑、压段末否定）之后，让一个**没参与改写**的模型对照新旧两稿，专查"新稿比旧稿多说了哪一层"。

```bash
cd <工作目录>          # 放入 旧稿.md、新稿.md，并把本目录的 prompt.md、schema.json 复制进来
codex exec -m gpt-6-sol -c 'model_reasoning_effort="xhigh"' -C . -s read-only \
  --skip-git-repo-check --ephemeral --output-schema schema.json -o out.json - < prompt.md
```

- 提示词不要告诉它上一轮查出过什么，否则就不是独立复核。
- 它说"高"的每一条，**回原始材料核**（判决原文、官方公布案情、法条官方文本）。它也会错，也会漏。
- 模型强弱差别很大。2026-09 同一份稿：gpt-5.6-luna 查出 16 条，没发现判例归因错误；
  gpt-6-sol（xhigh）查出何某案判旨、殷某桢案驳回理由两处"高"，回最高法与山东高院公布材料核实，都属实。
- CLI 太旧会不认识新模型（报 `Model metadata … not found` 与 `not supported when using Codex with a ChatGPT account`），先 `codex update`。
