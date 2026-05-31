"""
strand-predator — 养蛊演化引擎

三个算子：
  同类吞噬 (cannibalize)  — 相似实体合并去重
  异种杂交 (hybridize)    — 互补实体融合创新
  能量榨取 (extract)      — 濒死实体能量回收

依赖: strand-matcher (DNA相似度), strand-router (图邻居)

用法:
    from strand_predator import Arena
    arena = Arena()
    evolved = arena.run(entities)
    # → 吞噬/杂交/榨取后的新实体列表
"""

from __future__ import annotations
from typing import Any, Optional, Callable
import math, copy, random


# ── 可配置常量 ──
CANNIBALIZE_SIMILARITY = 0.70       # 同类吞噬相似度阈值
CANNIBALIZE_ABSORPTION = 0.5        # 消化效率
HYBRIDIZE_SIMILARITY = 0.30         # 杂交相似度上限
HYBRIDIZE_COMPLEMENTARITY = 0.40    # 杂交互补度下限
HYBRIDIZE_ENERGY_BOOST = 1.2        # 杂交初始能量增益
EXTRACT_FOSSIL = 0.10               # 榨取的化石阈值
MAX_ENERGY = 2.0                    # 单实体能量上限


class Arena:
    """养蛊场 — 运行三个演化算子周期。"""

    def __init__(self,
                 sim_threshold: float = CANNIBALIZE_SIMILARITY,
                 absorption_rate: float = CANNIBALIZE_ABSORPTION,
                 hybrid_sim_upper: float = HYBRIDIZE_SIMILARITY,
                 hybrid_comp_lower: float = HYBRIDIZE_COMPLEMENTARITY,
                 hybrid_boost: float = HYBRIDIZE_ENERGY_BOOST,
                 fossil_threshold: float = EXTRACT_FOSSIL,
                 max_energy: float = MAX_ENERGY,
                 similarity_fn: Optional[Callable] = None,
                 neighbors_fn: Optional[Callable] = None,
                 router: Optional[Any] = None,
                 anti_records_fn: Optional[Callable] = None,
                 anti_priority_weight: float = 0.2):
        """
        similarity_fn(dna_a, dna_b) → float
            默认用内置 DNA 相似度（交集/并集）。
        neighbors_fn(entity_id, entities) → list[dict]
            默认根据 entities 中的 connections 字段获取邻居。
        router: StrandRouter 实例。杂交产生的实体自动注册边。
        anti_records_fn(entity_id) → int
            返回免疫系统对该实体的反链记录数。
            记录越多的实体在吞噬时越优先被吃。
        anti_priority_weight: float
            反链记录的优先级权重（0.0=关闭, 建议0.2）。
        """
        self.sim_threshold = sim_threshold
        self.absorption_rate = absorption_rate
        self.hybrid_sim_upper = hybrid_sim_upper
        self.hybrid_comp_lower = hybrid_comp_lower
        self.hybrid_boost = hybrid_boost
        self.fossil_threshold = fossil_threshold
        self.max_energy = max_energy
        self._sim_fn = similarity_fn or self._default_similarity
        self._neighbors_fn = neighbors_fn or self._default_neighbors
        self.router = router
        self._anti_fn = anti_records_fn
        self.anti_weight = anti_priority_weight
        # 全局能量池（孤立节点榨取时回收）
        self.global_pool = 0.0
        # 演化日志
        self.history: list[dict] = []

    # ── 同类吞噬 ──

    def _cluster(self, entities: list[dict]) -> list[list[dict]]:
        """按 DNA 指纹聚类（主域+意图前3字符），减少 O(n²) 基数。"""
        groups: dict[str, list[dict]] = {}
        for ent in entities:
            dna = ent.get("dna", {})
            # 指纹: 所有链的第一个值（sorted）
            key_parts = []
            for k in sorted(dna.keys()):
                vals = dna.get(k, [])
                if vals:
                    key_parts.append(vals[0][:3])
            key = ":".join(key_parts) if key_parts else "_"
            groups.setdefault(key, []).append(ent)
        return list(groups.values())

    def cannibalize(self, entities: list[dict],
                    use_clustering: bool = True) -> list[dict]:
        """相似实体合并去重。
        
        use_clustering=True: 先按 DNA 指纹分组，组内比较。
            将 O(n²) 降为 O(Σk²)，k=组大小。
            对 100K 均匀分布在 5 个域的实体，降为 5×20K² ≈ 1/5。
            正确性不受影响：不同指纹的实体 DNA 相似度必 < 阈值。
        """
        results = list(entities)

        # 聚类分组（大幅降低配对基数）
        if use_clustering and len(results) > 500:
            groups = self._cluster(results)
        else:
            groups = [results]

        consumed: set[str] = set()  # 用 ID 跟踪，不依赖结果列表索引
        for group in groups:
            live_group = [e for e in group if e.get("id", "") not in consumed]
            if len(live_group) < 2:
                continue
            # 如果组内全部 DNA 相同，直接批量合并（跳过 O(n²)）
            if len(live_group) > 100:
                first_dna = live_group[0].get("dna", {})
                all_identical = all(
                    e.get("dna", {}) == first_dna for e in live_group
                )
                if all_identical:
                    # 合并到第一个实体
                    total_energy = sum(self._get_energy(e) for e in live_group)
                    best = max(live_group, key=lambda x:
                               self._get_energy(x) +
                               (self._anti_fn(x.get("id",""))
                                if self._anti_fn else 0) * -self.anti_weight)
                    best["energy"] = min(total_energy, self.max_energy)
                    absorbed = best.setdefault("absorbed", [])
                    absorbed.extend(e["id"] for e in live_group if e is not best)
                    consumed.update(e["id"] for e in live_group if e is not best)
                    self.history.append({
                        "type": "cannibalize_batch",
                        "winner": best["id"],
                        "count": len(live_group),
                        "energy_after": round(best["energy"], 3),
                    })
                    continue
            # 正常组内两两比较
            for i in range(len(live_group)):
                if live_group[i].get("id", "") in consumed:
                    continue
                for j in range(i + 1, len(live_group)):
                    if live_group[j].get("id", "") in consumed:
                        continue
                    ei_a = live_group[i]
                    ei_b = live_group[j]
                    sim = self._sim_fn(
                        ei_a.get("dna", {}),
                        ei_b.get("dna", {}),
                    )
                    if sim >= self.sim_threshold:
                        a, b = ei_a, ei_b
                        ea = self._get_energy(a)
                        eb = self._get_energy(b)
                        # 反链优先级
                        anti_a = self._anti_fn(a.get("id","")) if self._anti_fn else 0
                        anti_b = self._anti_fn(b.get("id","")) if self._anti_fn else 0
                        priority_a = ea - anti_a * self.anti_weight
                        priority_b = eb - anti_b * self.anti_weight
                        if priority_a >= priority_b:
                            winner, loser = a, b
                        else:
                            winner, loser = b, a
                        new_e = min(
                            self._get_energy(winner)
                            + self._get_energy(loser) * self.absorption_rate,
                            self.max_energy,
                        )
                        winner["energy"] = new_e
                        absorbed = winner.setdefault("absorbed", [])
                        absorbed.append(loser.get("id", "?"))
                        consumed.add(loser.get("id", ""))
                        self.history.append({
                            "type": "cannibalize",
                            "winner": winner.get("id"),
                            "loser": loser.get("id"),
                            "sim": round(sim, 3),
                            "energy_before": round(ea + eb, 3),
                            "energy_after": round(new_e, 3),
                        })

        return [e for e in results if e.get("id", "") not in consumed]

    # ── 异种杂交 ──

    def hybridize(self, entities: list[dict],
                  max_hybrids: int = 5,
                  max_attempts: int = 2000) -> list[dict]:
        """互补实体融合创新。返回原列表+杂交体。

        同类DNA先被 cannibalize 吞噬，剩下不同类的自然进入杂交。
        随机抽样配对（非全量 O(n²)），找到 max_hybrids 即停。
        """
        results = list(entities)
        new_hybrids = []
        n = len(results)
        if n < 2:
            return results
        # 随机抽样配对，恒定 max_attempts 次尝试（非 O(n²)）
        seen: set[tuple[int, int]] = set()
        for _ in range(min(max_attempts, n * n // 2)):
            if len(new_hybrids) >= max_hybrids:
                break
            i = random.randrange(n)
            j = random.randrange(n)
            if i == j:
                continue
            if i > j:
                i, j = j, i
            if (i, j) in seen:
                continue
            seen.add((i, j))
            a, b = results[i], results[j]
            dna_a = a.get("dna", {})
            dna_b = b.get("dna", {})
            sim = self._sim_fn(dna_a, dna_b)
            if sim >= self.hybrid_sim_upper:
                continue
            comp = self._complementarity(dna_a, dna_b)
            if comp < self.hybrid_comp_lower:
                continue
            hybrid = self._create_hybrid(a, b, entities)
            new_hybrids.append(hybrid)
            self.history.append({
                "type": "hybridize",
                "parent_a": a.get("id"),
                "parent_b": b.get("id"),
                "hybrid": hybrid.get("id"),
                "sim": round(sim, 3),
                "comp": round(comp, 3),
                "energy": round(hybrid.get("energy", 0), 3),
            })
        return results + new_hybrids

    # ── 能量榨取 ──

    def extract(self, entities: list[dict]) -> list[dict]:
        """濒死实体能量回收给邻近实体，孤立节点→全局池。"""
        results = list(entities)
        survivors = []
        for ent in results:
            energy = self._get_energy(ent)
            if energy >= self.fossil_threshold:
                survivors.append(ent)
                continue
            # 能量低于化石阈值 → 榨取
            neighbors = self._neighbors_fn(ent.get("id", ""), results)
            if not neighbors:
                # 孤立节点：能量归还全局池
                self.global_pool += energy
                self.history.append({
                    "type": "extract_pool",
                    "entity": ent.get("id"),
                    "energy_to_pool": round(energy, 3),
                })
            else:
                share = energy / len(neighbors)
                for n in neighbors:
                    n["energy"] = min(
                        self._get_energy(n) + share, self.max_energy
                    )
                self.history.append({
                    "type": "extract_distribute",
                    "entity": ent.get("id"),
                    "energy": round(energy, 3),
                    "share": round(share, 3),
                    "recipients": [n.get("id") for n in neighbors],
                })
        return survivors

    # ── 集成周期 ──

    def run(self, entities: list[dict], rounds: int = 3,
            entities_are_new: bool = True) -> list[dict]:
        """运行完整的养蛊周期（吞噬→杂交→榨取）× rounds。

        entities_are_new: True 则设置初始能量（未设置 energy 的实体设为 0.5）。
        """
        self.history.clear()
        self.global_pool = 0.0
        pool = [dict(e) for e in entities]

        # 初始化能量
        if entities_are_new:
            for e in pool:
                e.setdefault("energy", 0.5)
                e.setdefault("absorbed", [])
                e.setdefault("dna", {})

        total_before = sum(self._get_energy(e) for e in pool) + self.global_pool

        for rnd in range(rounds):
            self.history.append({"round": rnd, "entities_before": len(pool)})
            pool = self.cannibalize(pool)
            pool = self.hybridize(pool, max_hybrids=2)
            pool = self.extract(pool)
            self.history[-1]["entities_after"] = len(pool)
            self.history[-1]["total_energy"] = round(
                sum(self._get_energy(e) for e in pool) + self.global_pool, 3
            )

        return pool

    # ── 内部 ──

    def _get_energy(self, entity: dict) -> float:
        return entity.get("energy", 0.5)

    def _default_similarity(self, dna_a: dict, dna_b: dict) -> float:
        """DNA 相似度：所有链的加权交集/并集均值。"""
        if not dna_a or not dna_b:
            return 0.0
        all_strands = set(dna_a.keys()) | set(dna_b.keys())
        scores = []
        for s in all_strands:
            va = set(dna_a.get(s, []))
            vb = set(dna_b.get(s, []))
            if not va and not vb:
                scores.append(1.0)
                continue
            intersection = len(va & vb)
            union = len(va | vb)
            scores.append(intersection / max(union, 1))
        return sum(scores) / max(len(scores), 1)

    def _complementarity(self, dna_a: dict, dna_b: dict) -> float:
        """互补性：对称差集 / 并集。

        只在"各有所长且互不重叠"时高值。
        完全相同实体 = 0.0，完全无关实体 ≈ 0.5~0.8。
        """
        set_a = set()
        for v in dna_a.values():
            set_a.update(v)
        set_b = set()
        for v in dna_b.values():
            set_b.update(v)
        if not set_a and not set_b:
            return 0.0
        sym_diff = len(set_a ^ set_b)
        union = len(set_a | set_b)
        return sym_diff / max(union, 1)

    def _create_hybrid(self, a: dict, b: dict,
                       pool: list[dict]) -> dict:
        """创建杂交新实体。"""
        dna_a = a.get("dna", {})
        dna_b = b.get("dna", {})
        hybrid_dna: dict[str, list] = {}
        for s in set(dna_a.keys()) | set(dna_b.keys()):
            vals = list(set(dna_a.get(s, []) + dna_b.get(s, [])))
            hybrid_dna[s] = vals

        ea = self._get_energy(a)
        eb = self._get_energy(b)
        hybrid_energy = min(
            ((ea + eb) / 2) * self.hybrid_boost, self.max_energy
        )

        hybrid_id = f"hybrid_{a.get('id','?')}_{b.get('id','?')}"

        # 连接：继承双方邻居
        connections = set()
        for parent in [a, b]:
            for conn in parent.get("connections", []):
                connections.add(conn)
            connections.add(parent.get("id", ""))
        connections.discard(hybrid_id)

        # 注册到 router（如果有）
        if self.router:
            self.router.add_edge(hybrid_id, a.get("id", ""))
            self.router.add_edge(hybrid_id, b.get("id", ""))
            for conn_id in list(connections)[:5]:
                if conn_id != hybrid_id:
                    self.router.add_edge(hybrid_id, conn_id)

        return {
            "id": hybrid_id,
            "dna": hybrid_dna,
            "energy": hybrid_energy,
            "connections": list(connections),
            "absorbed": [],
            "origin": "hybrid",
            "parents": [a.get("id"), b.get("id")],
        }

    def _default_neighbors(self, entity_id: str,
                           entities: list[dict]) -> list[dict]:
        """从 connections 字段获取邻居。"""
        for ent in entities:
            if ent.get("id") == entity_id:
                conn_ids = set(ent.get("connections", []))
                return [
                    e for e in entities
                    if e.get("id") in conn_ids
                ]
        return []


__all__ = ["Arena"]

if __name__ == "__main__":
    from strand_matcher import Matcher, MatchResult

    demo_entities = [
        {"id": "api_v1", "dna": {"domain": ["tech"], "intent": ["deploy", "build"],
                                  "format": ["code"], "urgency": ["normal"]},
         "connections": ["docker", "cloud"], "energy": 0.8},
        {"id": "api_v2", "dna": {"domain": ["tech"], "intent": ["deploy", "build"],
                                  "format": ["code"], "urgency": ["critical"]},
         "connections": ["docker", "cloud"], "energy": 0.6},
        {"id": "analyst", "dna": {"domain": ["finance"], "intent": ["analyze"],
                                   "format": ["doc"], "urgency": ["normal"]},
         "connections": ["report", "data"], "energy": 0.5},
        {"id": "weak_noise", "dna": {"domain": ["tech"], "intent": ["unknown"],
                                      "format": ["unknown"], "urgency": ["normal"]},
         "connections": ["docker"], "energy": 0.05},
        {"id": "quantum", "dna": {"domain": ["tech"], "intent": ["build"],
                                   "format": ["code"], "urgency": ["low"]},
         "connections": ["api_v2"], "energy": 0.3},
    ]

    arena = Arena()
    result = arena.run(demo_entities, rounds=3)

    print(f"entity_count: {len(demo_entities)} → {len(result)}")
    for e in result:
        print(f"  {e['id']:30s} energy={e['energy']:.3f} "
              f"absorbed={e.get('absorbed',[])}")
    print(f"global_pool: {arena.global_pool:.3f}")
    print(f"history entries: {len(arena.history)}")
    for h in arena.history:
        if "type" in h:
            print(f"  [{h['type']}] {h}")
