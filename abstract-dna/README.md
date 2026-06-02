# Abstract DNA

**Structural matching that bypasses the semantic gap.**
99.9% coverage on 799 real queries. Zero LLM. Zero hallucination.

[中文版](./PAPER.zh.md) | [English](./PAPER.en.md)

## Quick Start

```bash
cd strand-algorithm/abstract-dna
```

```python
from src.pipeline import pipeline

result = pipeline("帮我装个nginx")
print(result['signals'])   # {'action:setup': 0.3, ...}
```

## Papers
- [English Paper](./PAPER.en.md) — Bypassing Semantic Understanding
- [中文论文](./PAPER.zh.md) — 跳过语义鸿沟的结构匹配引擎

## Results
- 799 real queries: 99.9% coverage
- 58 adversarial queries: 67% (correct rejections for noise)
- ~11ms per query, zero external dependencies

## License
MIT
