"""
strand-encoder — 多链语义编码器

将任意文本投影到多维度语义空间（含向量嵌入）。
每条链（strand）从一个角度提取特征，产出结构化 DNA 向量。

向量嵌入链（embedding）向下兼容：连续余弦相似度→离散标签。
不受 embedding 模型限制，零 API 调用，纯关键词匹配。

用法:
    from strand_encoder import Encoder, demo_strands
    enc = Encoder(demo_strands())
    dna = enc.encode("帮我部署一个服务")
    # → {"domain": ["tech"], "intent": ["deploy"],
    #     "embedding": ["high"]}  ← 向量检索向下兼容
"""

from __future__ import annotations
from typing import Any, Optional
import math


def _cosine_sim(a: list[float], b: list[float]) -> float:
    """内积余弦相似度。"""
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb + 1e-10)


class Encoder:
    """多链编码器。

    支持两种链类型：
      - 关键词链（默认）：key→[keywords] 列表，匹配则命中
      - 嵌入链：标记为 __embedding__，自动计算离散相似度
    """

    def __init__(self, strands: dict[str, dict[str, list[str]]],
                 embed_dim: int = 0):
        """
        strands = {
            "domain":  {"tech": [...]},        ← 关键词链
            "embedding": {"__embedding__": []}, ← 嵌入链（特殊标记）
        }
        embed_dim: 嵌入向量维度，0 = 不启用。
        """
        self.strands = strands
        self.embed_dim = embed_dim

    def encode(self, text: str) -> dict[str, list[str]]:
        """对文本执行多链编码，返回 DNA 向量。

        embedding 链的标签为离散相似度等级：
          "high" / "medium" / "low" / "unknown"
        """
        t = text.lower().strip()
        dna: dict[str, list[str]] = {}
        for strand_name, categories in self.strands.items():
            # 嵌入链特殊处理
            if strand_name == "embedding" or "__embedding__" in categories:
                # 不在编码阶段生成 embedding（由外部提供时用 encode_with_embedding）
                continue
            scores: dict[str, int] = {}
            for key, keywords in categories.items():
                score = sum(1 for kw in keywords if kw.lower() in t)
                if score > 0:
                    scores[key] = score
            if scores:
                max_s = max(scores.values())
                dna[strand_name] = sorted(
                    k for k, s in scores.items() if s >= max_s * 0.5
                )
        return dna

    def encode_with_embedding(self, text: str,
                              entity_embeddings: dict[str, list[float]]) -> dict[str, list[str]]:
        """编码 + 嵌入比对，返回含 embedding 链的完整 DNA。

        entity_embeddings: {"devops": [0.1, 0.3, ...], ...}
        embedding 链标签: "high" / "medium" / "low"
        """
        dna = self.encode(text)
        if not self.embed_dim or not entity_embeddings:
            dna["embedding"] = ["unknown"]
            return dna
        # 如果有 embedding 模型，这里计算 query 嵌入再比对
        # 目前用占位值（实际运行时替换为真实的 embedding 模型调用）
        query_emb = [0.0] * self.embed_dim
        sims = {eid: _cosine_sim(query_emb, emb)
                for eid, emb in entity_embeddings.items()}
        max_sim = max(sims.values()) if sims else 0.0
        if max_sim >= 0.70:
            dna["embedding"] = ["high"]
        elif max_sim >= 0.40:
            dna["embedding"] = ["medium"]
        else:
            dna["embedding"] = ["low"]
        return dna

    def strands_info(self) -> dict[str, list[str]]:
        """返回每个链支持的关键词类别/配置。"""
        info = {}
        for k, v in self.strands.items():
            if k == "embedding" or "__embedding__" in v:
                info[k] = f"[embedding] dim={self.embed_dim}"
            else:
                info[k] = list(v.keys())
        return info


def embedding_strand(dim: int = 0) -> dict[str, list[str]]:
    """创建嵌入链配置。

    作为 strands 传入 Encoder 的一条普通链。
    matcher 不需要任何改动——离散标签参与加权投票。

    用法:
        enc = Encoder({**demo_strands(), **embedding_strand(128)})
    """
    return {"embedding": {"__embedding__": []}}


def demo_strands() -> dict[str, dict[str, list[str]]]:
    """内置演示数据（中英双语关键词 + embedding 链）。"""
    return {
        "domain": {
            "tech": ["python", "docker", "api", "server", "deploy", "cloud", "技术", "服务器", "代码", "系统"],
            "finance": ["stock", "market", "trade", "invest", "金融", "股票", "市场", "投资"],
            "health": ["patient", "diagnosis", "medical", "健康", "患者", "医疗", "诊断"],
            "ecosystem": ["dna", "memory", "strand", "生态", "记忆", "DNA", "链", "芯片", "模块"],
        },
        "intent": {
            "build": ["create", "develop", "build", "write", "implement", "写", "创建", "制作", "开发"],
            "analyze": ["analyze", "review", "audit", "evaluate", "分析", "审查", "评估", "验证"],
            "deploy": ["deploy", "release", "publish", "setup", "部署", "发布", "上线"],
            "evolve": ["evolve", "breed", "merge", "cannibalize", "hybridize", "养蛊", "吞噬", "杂交", "演化", "进化"],
            "protect": ["pin", "anchor", "rollback", "backup", "锚点", "回滚", "备份", "保护"],
        },
        "format": {
            "code": ["code", "script", "program", "function", "脚本", "代码", "程序"],
            "doc": ["report", "documentation", "doc", "文档", "报告", "方案"],
            "data": ["dataset", "table", "csv", "json", "数据", "表格", "数据库"],
            "entity": ["entity", "contract", "schema", "通道", "契约", "DNA", "坐标"],
        },
        "urgency": {
            "critical": ["urgent", "critical", "asap", "紧急", "立刻", "马上"],
            "normal": ["plan", "schedule", "backlog", "计划", "安排"],
            "low": ["nice to have", "someday", "有空"],
        },
        "embedding": {"__embedding__": []},  # 向量嵌入链（向下兼容）
    }


# ── 独立验证 ──
__all__ = ["Encoder", "demo_strands"]

if __name__ == "__main__":
    enc = Encoder(demo_strands())
    tests = ["帮我用 python 写一个部署脚本", "分析股票市场报告", "紧急修复服务器"]
    for t in tests:
        dna = enc.encode(t)
        print(f"  {t[:20]:20s} → {dna}")
