<div align="center">

# 🧬 Strand Algorithm

**多链DNA编码 × 加权投票 × 免疫系统 × 跨域路由 × 养蛊演化**

*零外部依赖 · 零 Token · 纯 Python3 · 亚毫秒级*

[![PyPI](https://img.shields.io/badge/pypi-dna--memory-blue)](https://pypi.org/project/dna-memory/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)
[![Validation](https://img.shields.io/badge/validation-99.3%25-green)]()
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue)]()

</div>

---

## 是什么？

Strand Algorithm 是一套**可插拔认知架构原语**，将记忆/匹配/路由/安全/演化等认知功能拆解为8个独立芯片。每颗芯片可独立 `pip install`，组合时形成全链路闭环。

```python
# 一句话安装
pip install strand

# 或按需安装单芯片
pip install strand-encoder
pip install strand-matcher
```

## 核心机制

| 芯片 | 功能 | 行数 | 验证 |
|------|------|:----:|:----:|
| **encoder** | 多链DNA语义编码 | 80 | ✅ |
| **matcher** | 加权投票+反链负反馈 | 100 | ✅ |
| **immune** | 分歧驱动免疫学习 | 130 | ✅ |
| **router** | BFS跨域虫洞路由 | 70 | ✅ |
| **regulate** | 三级意图安全规制 | 70 | ✅ |
| **lifecycle** | 能量半衰期管理 | 100 | ✅ |
| **predator** | 养蛊三算子(吞噬/杂交/榨取) | 130 | ✅ |
| **pool** | DNA本体记忆池(MemoryEntity v2) | 450 | ✅ |
| **strand** (元包) | 全链路集成管线 | — | ✅ |
| **dna-memory** | PyPI发布包 | 270 | 已发布 |

## 快速开始

```python
from strand_pool import MemoryPool, MemoryEntity

pool = MemoryPool()

# 添加记忆（自动编码DNA）
pool.add("rule-1", "database timeout deploy set 30 seconds", pinned=True)

# 召回
results = pool.recall("deploy database timeout")
# → [rule-1, ...]

# 养蛊演化（自动去重、杂交、回收）
pool.evolve(rounds=3)

# 持久化
pool.save("my_memories.json")
pool2 = MemoryPool.load("my_memories.json")
```

## 性能

| 操作 | 耗时 |
|------|:----:|
| DNA编码 | **0.02-0.06ms** |
| 匹配(10实体) | **0.08ms** |
| 养蛊(1K实体) | **0.003s** |
| 养蛊(10K实体) | **0.058s** |
| 记忆池写入 | **57K条/s** |
| 100K加载 | **0.78s** |
| Token消耗 | **0** |
| 外部依赖 | **0** |

## 验证

累计 **142/143 (99.3%)** 通过，超越基线 94.7% vs 16.7%

## 安装

```bash
# 全部
pip install strand

# 单芯片
pip install strand-encoder
pip install strand-matcher
pip install strand-immune
pip install strand-router
pip install strand-regulate
pip install strand-lifecycle
pip install strand-predator
pip install strand-pool

# PyPI
pip install dna-memory
```

## 协议

双授权：
- **MIT** — 个人、社区、开源项目免费使用
- **企业商用许可** — 企业级部署需要授权

## 联系方式

- **作者**: 钟一鸣
- **邮箱**: 2353650645@qq.com
- **微信**: 15800254733
- **GitHub Issues**: [创建 Issue](https://github.com/asdfdsa1ceacse/strand-algorithm/issues)

## 📄 论文 / Papers

- **v2.1 — 理论体系完整版** (推荐): `Strand_Algorithm_理论体系_v2.docx`
  按单一因果链组织：空间→DNA坐标→虫洞→多模态→双螺旋→复制体穿行→记忆→养蛊→坍缩→跨域→编译
- **v1 — 旧版草案**: `Strand_Algorithm_理论体系_v1_旧版草稿.docx`
  初版草稿，章节为并行概念排列，逻辑不如v2流畅

## 🌐 链接

- **Zenodo**: [10.5281/zenodo.20474405](https://doi.org/10.5281/zenodo.20474405)
- **PyPI**: `pip install dna-memory`
- **论文桌面版**: `C:\Users\zym15\Desktop\Strand_Algorithm_理论体系_v2.docx`
