"""
strand — 全链路集成元包

组合 6 个独立芯片为一个闭环管线。

每个芯片独立可跑，但一起使用时：
  编码 → 匹配 → 路由 | 分歧 → 免疫学习 | 执行前 → 规制
                                                      | 实体 → 生命周期管理

用法:
    from strand import pipeline
    result = pipeline("帮我部署一个服务")
    # → {"match": ..., "route": ..., "regulate": ..., ...}
"""

from __future__ import annotations
import json, time
from typing import Optional, Any

# 尝试导入各独立芯片（软依赖）
try:
    from strand_encoder import Encoder, demo_strands
except ImportError:
    Encoder = None

try:
    from strand_matcher import Matcher, MatchResult
except ImportError:
    Matcher = None

try:
    from strand_immune import ImmuneSystem
except ImportError:
    ImmuneSystem = None

try:
    from strand_router import Router
except ImportError:
    Router = None

try:
    from strand_regulate import Regulator, demo_principles
except ImportError:
    Regulator = None

try:
    from strand_lifecycle import Lifecycle
except ImportError:
    Lifecycle = None


class Pipeline:
    """全链路管线 — 编码 → 匹配 → 路由 → 规制 → 免疫学习 → 生命周期。"""

    def __init__(self):
        self.encoder = Encoder(demo_strands()) if Encoder else None
        self.matcher = Matcher({
            "domain": 0.25, "intent": 0.20, "format": 0.15,
            "urgency": 0.10, "entity": 0.10, "embedding": 0.20,
        }) if Matcher else None
        self.immune = ImmuneSystem() if ImmuneSystem else None
        self.router = Router() if Router else None
        self.regulator = Regulator(
            demo_principles()
        ) if Regulator else None
        self.lifecycle = Lifecycle() if Lifecycle else None
        self.entities: list[dict] = []

    def add_entities(self, entities: list[dict]):
        """注册候选实体。"""
        self.entities = entities
        if self.router:
            for ent in entities:
                self._add_routes_for(ent)

    def _add_routes_for(self, ent: dict):
        eid = ent.get("id", "")
        for neighbor in ent.get("connections", []):
            self.router.add_edge(eid, neighbor)

    def run(self, query: str, anti_chains: Optional[dict] = None) -> dict:
        """全链路执行。"""
        start = time.perf_counter()
        result: dict[str, Any] = {"query": query, "latency_ms": 0.0}

        # 1) 编码
        if self.encoder:
            dna = self.encoder.encode(query)
            result["dna"] = dna

        # 2) 匹配
        match_result = None
        if self.matcher and self.encoder:
            r = self.matcher.match(
                dna, self.entities, anti_chains=anti_chains,
                raw_query=query
            )
            if r is not None:
                result["match"] = {
                    "entity": r.entity_id,
                    "score": r.score,
                    "chain_scores": r.chain_scores,
                    "anti_hits": r.anti_hits,
                }
                match_result = r
            else:
                result["match"] = {
                    "entity": None, "score": 0.0,
                    "chain_scores": {}, "anti_hits": [],
                }

        # 3) 规制检查
        if self.regulator:
            reg = self.regulator.check(query)
            result["regulate"] = {
                "blocked": reg.blocked,
                "hits_count": len(reg.hits),
                "hits": reg.hits,
            }

        # 4) 路由展开
        if self.router and match_result and match_result.entity_id:
            routes = self.router.route(
                match_result.entity_id, hops=2
            )
            result["routes"] = routes

        # 5) 生命周期
        if self.lifecycle and match_result and match_result.entity_id:
            st = self.lifecycle.status(match_result.entity_id)
            if st:
                result["lifecycle"] = {
                    "energy": st.energy,
                    "alive": st.alive,
                    "age_days": st.age_days,
                }

        result["latency_ms"] = round(
            (time.perf_counter() - start) * 1000, 2
        )
        return result


def pure_match(query: str, entities: list[dict],
               anti_chains: Optional[dict] = None) -> dict:
    """纯匹配模式 — 只用编码+匹配，不跑全链路。"""
    p = Pipeline()
    p.add_entities(entities)
    return p.run(query, anti_chains)


__all__ = ["Pipeline", "pure_match"]
__version__ = "0.1.0"

if __name__ == "__main__":
    ents = [
        {"id": "devops",
         "dna": {"domain": ["tech"], "intent": ["deploy", "build"],
                 "format": ["code"], "urgency": ["critical"], "entity": []},
         "connections": ["cloud", "docker"]},
        {"id": "analyst",
         "dna": {"domain": ["finance"], "intent": ["analyze"],
                 "format": ["doc"], "urgency": ["normal"], "entity": []},
         "connections": ["report", "data"]},
    ]
    # 先单独测试纯匹配
    r = pure_match("帮我部署系统", ents)
    print(f"纯匹配: {json.dumps(r, ensure_ascii=False, indent=2)}")
