"""
strand-matcher — 独立决策引擎

对候选实体执行加权多链投票匹配 + 可选反链负反馈抑制。
单独使用时不依赖其他包，只需输入 DNA 向量和候选实体。

用法:
    from strand_matcher import Matcher
    # 配置 3 条链，权重和为 1.0
    m = Matcher(strand_weights={"domain": 0.4, "intent": 0.3, "format": 0.3})
    result = m.match(query_dna, entities, anti_chains=anti)
    # → MatchResult(entity="xxx", score=0.72, chain_scores={...})
"""

from __future__ import annotations
from typing import Optional, Any
from dataclasses import dataclass, field


@dataclass
class MatchResult:
    entity_id: Optional[str] = None
    score: float = 0.0
    chain_scores: dict[str, float] = field(default_factory=dict)
    anti_hits: list[str] = field(default_factory=list)


class Matcher:
    """加权多链投票匹配器，附带反链负反馈抑制。"""

    def __init__(
        self,
        strand_weights: dict[str, float],
        threshold: float = 0.10,
        anti_penalty: float = 0.10,
        anti_max: float = 0.35,
        entity_boost: float = 2.0,
    ):
        self.weights = strand_weights
        self.threshold = threshold
        self.anti_penalty = anti_penalty
        self.anti_max = anti_max
        self.entity_boost = entity_boost
        self._entity_strands: set[str] = set()

    def mark_entity_strand(self, name: str):
        """将某条链标记为实体链（名称匹配时 boost）。"""
        self._entity_strands.add(name)

    def match(
        self,
        query_dna: dict[str, list[str]],
        entities: list[dict[str, Any]],
        anti_chains: Optional[dict[str, list[dict]]] = None,
        raw_query: Optional[str] = None,
    ) -> MatchResult:
        """
        query_dna:  Encoder.encode() 的输出
        entities:   [{"id": "foo", "dna": {"domain": [...], ...}}, ...]
        anti_chains: {"foo": [{"word": "report", ...}], ...}
        raw_query:  Optional. 原始查询文本，用于中文反链词匹配。
                    反链词同时检查 DNA 向量和原始文本。
        """
        best = MatchResult()
        for ent in entities:
            eid = ent.get("id", "")
            ent_dna = ent.get("dna", {})
            total = 0.0
            chain_scores: dict[str, float] = {}
            for strand, weight in self.weights.items():
                q_vals = set(query_dna.get(strand, ["unknown"]))
                h_vals = set(ent_dna.get(strand, []))
                if not h_vals:
                    continue
                overlap = q_vals & h_vals
                if overlap:
                    score = len(overlap) / max(len(q_vals), 1)
                    if strand in self._entity_strands:
                        # 实体链检查名称匹配或 DNA 实体匹配
                        q_lower = " ".join(query_dna.get(strand, []))
                        if eid.lower() in q_lower or (
                            "entity" in query_dna
                            and eid.lower()
                            in [e.lower() for e in query_dna["entity"]]
                        ):
                            score *= self.entity_boost
                    chain_scores[strand] = score * weight
                    total += chain_scores[strand]

            # 反链负反馈抑制（同时检查 DNA 向量和原始文本）
            anti_hits: list[str] = []
            if anti_chains and eid in anti_chains:
                q_text = " ".join(
                    v for vals in query_dna.values() for v in vals
                )
                anti_candidates = [q_text]
                if raw_query:
                    anti_candidates.append(raw_query.lower().strip())
                for entry in anti_chains[eid]:
                    for source in anti_candidates:
                        if entry["word"] in source:
                            anti_hits.append(entry["word"])
                            break
                if anti_hits:
                    penalty = min(
                        len(anti_hits) * self.anti_penalty, self.anti_max
                    )
                    total -= penalty

            if total > best.score and total >= self.threshold:
                best = MatchResult(
                    entity_id=eid,
                    score=total,
                    chain_scores=chain_scores,
                    anti_hits=anti_hits,
                )
        return best if best.score >= self.threshold else None


__all__ = ["Matcher", "MatchResult"]

if __name__ == "__main__":
    from strand_encoder import Encoder, demo_strands
    enc = Encoder(demo_strands())
    matcher = Matcher({"domain": 0.4, "intent": 0.3, "format": 0.3})
    entities = [
        {"id": "devops", "dna": {"domain": ["tech"], "intent": ["deploy", "build"], "format": ["code"]}},
        {"id": "analyst", "dna": {"domain": ["finance"], "intent": ["analyze"], "format": ["doc"]}},
    ]
    q = "帮我部署系统"
    r = matcher.match(enc.encode(q), entities)
    print(f"  {q} → {r.entity_id} ({r.score})")
