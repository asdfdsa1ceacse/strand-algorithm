"""
strand-lifecycle — 独立生命周期管理器（能量半衰期 + 化石复活）

给实体按物种（species）配置差异化半衰期。
能量按 Ebbinghaus 公式衰减，永不归零（0.1 地板）。
衰减到 fossil 阈值的实体可被 ghost hit 复活。

用法:
    from strand_lifecycle import Lifecycle
    lc = Lifecycle()
    lc.add_entity("word_X", species="migration", created="2026-06-01")
    status = lc.status("word_X")
    # → {"alive": True, "energy": 0.85, "age_days": 1, ...}
"""

from __future__ import annotations
import time, math
from typing import Optional
from dataclasses import dataclass, field


# 默认物种配置
DEFAULT_SPECIES = {
    "migration": {"half_life": 14, "fossil_threshold": 0.15},
    "grown":     {"half_life": 30, "fossil_threshold": 0.10},
    "core":      {"half_life": 365, "fossil_threshold": 0.05},
}


@dataclass
class EntityStatus:
    entity_id: str
    species: str
    energy: float
    age_days: float
    alive: bool
    fossil: bool


class Lifecycle:
    """基于半衰期和化石机制的实体生命周期管理。"""

    def __init__(self, species_config: Optional[dict] = None):
        self.species = species_config or DEFAULT_SPECIES
        self.entities: dict[str, dict] = {}
        self.fossils: dict[str, dict] = {}

    def add_entity(self, entity_id: str, species: str = "grown",
                   created: Optional[str] = None, data: Optional[dict] = None):
        """注册一个实体的生命周期。"""
        if created:
            t = time.mktime(time.strptime(created, "%Y-%m-%d"))
        else:
            t = time.time()
        self.entities[entity_id] = {
            "species": species,
            "created": t,
            "data": data or {},
        }

    def status(self, entity_id: str) -> Optional[EntityStatus]:
        """查询实体的当前能量状态。"""
        ent = self.entities.get(entity_id) or self.fossils.get(entity_id)
        if not ent:
            return None
        cfg = self.species.get(
            ent["species"], {"half_life": 30, "fossil_threshold": 0.10}
        )
        age_seconds = time.time() - ent["created"]
        age_days = age_seconds / 86400
        hl = cfg["half_life"]
        energy = 1.0 * math.exp(-math.log(2) * age_days / hl)
        energy = max(0.1, round(energy, 3))  # 地板保护
        alive = energy >= cfg.get("fossil_threshold", 0.10)
        return EntityStatus(
            entity_id=entity_id,
            species=ent["species"],
            energy=energy,
            age_days=round(age_days, 1),
            alive=alive,
            fossil=not alive,
        )

    def decay(self) -> list[dict]:
        """执行一次全局衰减，返回新进入化石状态的实体。"""
        new_fossils = []
        for eid, ent in list(self.entities.items()):
            st = self.status(eid)
            if st and st.fossil:
                new_fossils.append(eid)
                self.fossils[eid] = ent
                del self.entities[eid]
        return new_fossils

    def revive(self, entity_id: str,
               new_species: Optional[str] = None) -> Optional[EntityStatus]:
        """从化石状态复活一个实体（ghost hit）。"""
        if entity_id not in self.fossils:
            return None
        ent = self.fossils.pop(entity_id)
        if new_species:
            ent["species"] = new_species
        ent["created"] = time.time()  # 重置时钟
        self.entities[entity_id] = ent
        return self.status(entity_id)

    def report(self) -> dict:
        """生成当前状态报告。"""
        alive = sum(
            1 for eid in self.entities
            if (st := self.status(eid)) and st.alive
        )
        fossil = len(self.fossils)
        return {
            "active": len(self.entities),
            "alive": alive,
            "fossil": fossil,
            "species": {k: {
                "half_life": v["half_life"],
                "fossil_threshold": v["fossil_threshold"],
            } for k, v in self.species.items()},
        }


__all__ = ["Lifecycle", "EntityStatus", "DEFAULT_SPECIES"]

if __name__ == "__main__":
    lc = Lifecycle()
    lc.add_entity("temp_word", species="migration", created="2026-05-20")
    lc.add_entity("stable_knowledge", species="core", created="2026-06-01")
    lc.add_entity("auto_learned", species="grown", created="2026-05-28")
    for eid in ["temp_word", "stable_knowledge", "auto_learned"]:
        st = lc.status(eid)
        print(f"  {eid:20s} energy={st.energy:.3f} alive={st.alive}")
    print(f"报告: {lc.report()}")
