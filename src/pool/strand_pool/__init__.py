"""
strand-pool — DNA本体记忆存储层

用法:
    from strand_pool import MemoryPool
    pool = MemoryPool()
    pool.add("规则-1", "数据库连接超时设为30秒")
    pool.recall("数据库超时怎么办")
    pool.evolve()
    pool.save("memories.json")
"""
from __future__ import annotations
from typing import Optional, Any, Callable
import json, time, copy, os

from strand_pool.entity import MemoryEntity, MemorySource, make_dna_strand, normalize_energy
from strand_encoder import Encoder, demo_strands
from strand_matcher import Matcher, MatchResult
from strand_predator import Arena
from strand_lifecycle import Lifecycle

__all__ = ["MemoryPool", "MemoryEntity", "MemorySource"]

LegacyAdapter = Callable[[str, int], list[dict]]


class MemoryPool:
    """DNA本体记忆池。记忆 = Entity + DNA。
    
    支持四种来源: hindsight, dna_memory, hub_3d, hermes
    迁移期可通过 legacy_fallback 兜底。
    """

    def __init__(self, strands: Optional[dict] = None,
                 weights: Optional[dict] = None,
                 sim_threshold: float = 0.70,
                 legacy_fallback: Optional[LegacyAdapter] = None):
        self.encoder = Encoder(strands or demo_strands())
        self.matcher = Matcher(weights or {
            "domain": 0.25, "intent": 0.20, "format": 0.15,
            "urgency": 0.10, "entity": 0.10, "embedding": 0.20,
        })
        self.predator = Arena(sim_threshold=sim_threshold)
        self.lifecycle = Lifecycle()
        self.entities: list[dict] = []
        self.pinned: set[str] = set()
        self._fallback = legacy_fallback  # 迁移期安全网
        self._fallback_count = 0          # 连续fallback计数
        self._version = 0

    # ── 核心接口 ──

    def add(self, eid: str, text: str,
            source: MemorySource = "hermes",
            pinned: bool = False,
            energy: float = 0.5,
            meta: Optional[dict] = None) -> dict:
        """添加一条记忆。自动编码DNA。"""
        dna = self.encoder.encode(text)
        dna_strand = make_dna_strand(*[
            f"{k}:{v}" for k, vals in dna.items() for v in vals
        ])
        entity = {
            "id": eid, "text": text, "dna": dna, "dna_strand": dna_strand,
            "energy": normalize_energy(energy, source),
            "pinned": pinned, "source": source,
            "meta": meta or {}, "created": time.time(),
            "absorbed": [], "connections": [],
        }
        self.entities.append(entity)
        if pinned:
            self.pinned.add(eid)
        return entity

    def add_entity(self, entity: MemoryEntity) -> dict:
        """直接添加一个 MemoryEntity。"""
        # 展平 DNA tuple 为 dict 格式用于匹配器
        dna_dict: dict[str, list[str]] = {}
        for strand in entity.dna:
            if ":" in strand:
                k, v = strand.split(":", 1)
                dna_dict.setdefault(k, []).append(v)
        ent = {
            "id": entity.id, "text": entity.content,
            "dna": dna_dict, "dna_strand": entity.dna,
            "energy": entity.energy, "pinned": entity.pinned,
            "source": entity.source,
            "meta": dict(entity.metadata) if entity.metadata else {},
            "created": entity.created_at,
            "superseded_by": entity.superseded_by,
            "absorbed": [], "connections": [],
        }
        self.entities.append(ent)
        if entity.pinned:
            self.pinned.add(entity.id)
        return ent

    def recall(self, query: str, top_k: int = 5) -> list[dict]:
        """召回相关记忆。新引擎无结果时触发 legacy_fallback。
        含性能监控：P99 >500ms 自动告警。
        """
        _t0 = time.perf_counter()
        dna = self.encoder.encode(query)
        scored = []
        for ent in self.entities:
            r = self.matcher.match(dna, [ent])
            if r is not None:
                scored.append((r.score, ent))
        scored.sort(reverse=True, key=lambda x: x[0])
        results = [ent for _, ent in scored[:top_k]]

        # 性能监控
        _elapsed = time.perf_counter() - _t0
        if _elapsed > 0.500:
            import warnings
            warnings.warn(
                f"recall() P99 breach: {_elapsed*1000:.0f}ms for "
                f"{len(self.entities)} entities (threshold 500ms)"
            )

        # fallback 兜底
        if not results and self._fallback:
            self._fallback_count += 1
            results = self._fallback(query, top_k)
            if self._fallback_count >= 3:
                import warnings
                warnings.warn(
                    f"MemoryPool: {self._fallback_count} consecutive fallbacks. "
                    "Consider pause evolve() to prevent error spread."
                )
        else:
            self._fallback_count = 0
        return results

    def evolve(self, rounds: int = 1) -> None:
        pinned_ents = [e for e in self.entities if e["id"] in self.pinned]
        normal_ents = [e for e in self.entities if e["id"] not in self.pinned]
        if not normal_ents:
            return
        evolved = self.predator.run(normal_ents, rounds=rounds)
        self.entities = pinned_ents + evolved
        self._version += 1

    def remove(self, eid: str) -> bool:
        if eid in self.pinned:
            return False
        before = len(self.entities)
        self.entities = [e for e in self.entities if e["id"] != eid]
        self.pinned.discard(eid)
        return len(self.entities) < before

    def count(self) -> int:
        return len(self.entities)

    def get_version_chain(self, eid: str) -> list[str]:
        """获取实体的版本链（含防环检测）。
        返回 [最新版, 旧版, 更旧版, ...]。
        成环时截断并告警。
        """
        chain: list[str] = []
        visited: set[str] = set()
        current = eid
        while current is not None:
            if current in visited:
                import warnings
                warnings.warn(
                    f"superseded_by 成环: {'→'.join(chain + [current])} "
                    f"[{len(chain)}步后回到{current}]"
                )
                break
            visited.add(current)
            chain.append(current)
            ent = next((e for e in self.entities if e.get("id") == current), None)
            if ent is None:
                break
            current = ent.get("superseded_by")
        return chain

    # ── 四种来源的迁移导入 ──

    @classmethod
    def from_legacy_hindsight(cls, records: list[dict],
                              embedding_dim: int = 0,
                              **kwargs) -> "MemoryPool":
        """从 Hindsight 向量记录导入。"""
        pool = cls(**kwargs)
        for i, rec in enumerate(records):
            text = rec.get("content", rec.get("text", ""))
            confidence = rec.get("score", rec.get("confidence", 0.5))
            ent = MemoryEntity(
                id=f"hindsight_{i}",
                dna=(),  # 初始无DNA，等待下次encode补全
                content=text,
                energy=normalize_energy(confidence, "hindsight"),
                pinned=False,
                source="hindsight",
                created_at=rec.get("created_at", time.time()),
            )
            pool.add_entity(ent)
        return pool

    @classmethod
    def from_legacy_dna_memory(cls, records: list[dict],
                               **kwargs) -> "MemoryPool":
        """从 dna-memory 引擎记录导入（已有DNA片段）。"""
        pool = cls(**kwargs)
        for i, rec in enumerate(records):
            text = rec.get("text", rec.get("content", ""))
            raw_dna = rec.get("dna", {})
            dna_strand = make_dna_strand(*[
                f"{k}:{v}" for k, vals in raw_dna.items() for v in vals
            ])
            ent = MemoryEntity(
                id=f"dna_mem_{i}",
                dna=dna_strand,
                content=text,
                energy=normalize_energy(rec.get("energy", 0.5), "dna_memory"),
                pinned=rec.get("pinned", False),
                source="dna_memory",
                created_at=rec.get("created_at", time.time()),
            )
            pool.add_entity(ent)
        return pool

    @classmethod
    def from_legacy_hub_3d(cls, nodes: list[dict],
                           **kwargs) -> "MemoryPool":
        """从 3D 记忆 Hub 图节点导入。"""
        pool = cls(**kwargs)
        for i, node in enumerate(nodes):
            text = node.get("label", node.get("content", ""))
            tags = node.get("tags", [])
            connections = node.get("connections", [])
            dna_strand = make_dna_strand(*[
                f"tag:{t}" for t in tags
            ] + [f"conn:{c}" for c in connections[:10]])
            ent = MemoryEntity(
                id=f"hub_3d_{i}",
                dna=dna_strand,
                content=text,
                energy=normalize_energy(node.get("weight", 0.5), "hub_3d"),
                pinned=node.get("pinned", False),
                source="hub_3d",
                created_at=node.get("created_at", time.time()),
            )
            pool.add_entity(ent)
        return pool

    # ── 持久化 ──

    def save(self, path: str) -> None:
        """原子写入。先写临时文件再 rename，防止断电截断。"""
        data = {
            "version": self._version,
            "pinned": list(self.pinned),
            "entities": self._serialize_entities(self.entities),
            "saved_at": time.time(),
        }
        import tempfile
        tmp = tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=os.path.dirname(path) or ".",
            prefix=".pool_tmp_", suffix=".json", delete=False)
        try:
            json.dump(data, tmp, ensure_ascii=False, indent=2)
            tmp.close()
            os.replace(tmp.name, path)
        except Exception:
            # 清理临时文件
            try: os.unlink(tmp.name)
            except OSError: pass
            raise

    @classmethod
    def load(cls, path: str, **kwargs) -> "MemoryPool":
        pool = cls(**kwargs)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        pool.entities = pool._deserialize_entities(data.get("entities", []))
        pool.pinned = set(data.get("pinned", []))
        pool._version = data.get("version", 0)
        return pool

    def _serialize_entities(self, ents):
        return [{
            k: v for k, v in e.items()
            if k in ("id","text","dna","dna_strand","energy","pinned",
                     "source","meta","created","superseded_by","absorbed")
        } for e in ents]

    def _deserialize_entities(self, data):
        for e in data:
            e.setdefault("absorbed", [])
            e.setdefault("connections", [])
            e.setdefault("source", "hermes")
            e.setdefault("pinned", False)
            e.setdefault("superseded_by", None)
            e.setdefault("meta", {})
        return data
