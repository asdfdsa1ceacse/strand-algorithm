"""
MemoryEntity v2 — 修订后统一记忆契约

修订 (vs v1):
  1. metadata: dict — 承载 spatial/temporal 等扩展属性
  2. superseded_by: Optional[str] — 版本指针，避免全文版本链膨胀
  3. normalize_dna() — 嵌套展平为 layer:N 前缀元组
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Literal, Optional
import time, hashlib, json

MemorySource = Literal["hindsight", "dna_memory", "hub_3d", "hermes"]

@dataclass(frozen=True)
class MemoryEntity:
    """v2 统一记忆实体。"""

    id: str
    dna: tuple[str, ...]          # 已 normalize_dna() 处理，保证 hashable
    content: str                  # 当前有效版本的内容
    energy: float                 # [0.0, 1.0]
    pinned: bool                  # 锚点标记，免疫 cannibalize
    source: MemorySource          # 来源标记永久保留
    created_at: float             # Unix 时间戳
    superseded_by: Optional[str] = None   # 版本指针，None=当前版本
    metadata: Optional[dict] = None       # 扩展属性（spatial/temporal/legacy_vec 等）

    def __post_init__(self):
        if not 0.0 <= self.energy <= 1.0:
            raise ValueError(f"energy must be [0,1], got {self.energy}")
        if not isinstance(self.dna, tuple):
            raise TypeError(f"dna must be tuple, got {type(self.dna)}")
        for item in self.dna:
            if not isinstance(item, str):
                raise TypeError(f"dna items must be str, got {type(item)}")

    # ── 序列化 ──

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "dna": list(self.dna) if self.dna else [],
            "content": self.content,
            "energy": self.energy,
            "pinned": self.pinned,
            "source": self.source,
            "created_at": self.created_at,
            "superseded_by": self.superseded_by,
            "metadata": dict(self.metadata) if self.metadata else None,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "MemoryEntity":
        if isinstance(d.get("dna"), list):
            d["dna"] = tuple(d["dna"])
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    def fingerprint(self) -> str:
        raw = f"{self.content}::{':'.join(self.dna)}"
        return hashlib.md5(raw.encode()).hexdigest()

    # ── DNA 归一化 ──

    @staticmethod
    def normalize_dna(raw_dna) -> tuple[str, ...]:
        """将各种来源的 DNA 统一为可哈希的 tuple[str, ...]。

        支持:
          - dict: {"domain":["tech"],"intent":["deploy"]} → ("domain:tech","intent:deploy")
          - list/tuple: ["A", ["B","C"]] → ("A", "layer1:B", "layer1:C")
          - str: 直接作为单元素
          - 混合嵌套: 递归展平

        嵌套深度通过 layer1:/layer2: 前缀保留，可复原。
        """
        results: list[str] = []

        def _flatten(item, depth=0):
            prefix = f"layer{depth}:" if depth > 0 else ""
            if isinstance(item, dict):
                for k, vals in item.items():
                    # dict 键值对：k:val
                    if isinstance(vals, (list, tuple)):
                        for v in vals:
                            if isinstance(v, str):
                                results.append(f"{k}:{v}")
                            else:
                                results.append(f"{k}:{prefix}{repr(v)}")
                    elif isinstance(vals, str):
                        results.append(f"{k}:{prefix}{vals}")
                    else:
                        _flatten(vals, depth + 1)
            elif isinstance(item, (list, tuple)):
                for v in item:
                    if isinstance(v, str):
                        results.append(f"{prefix}{v}")
                    elif isinstance(v, (list, tuple)):
                        _flatten(v, depth + 1)
                    elif isinstance(v, dict):
                        _flatten(v, depth + 1)
                    else:
                        results.append(f"{prefix}{repr(v)}")
            elif isinstance(item, str):
                results.append(f"{prefix}{item}")
            else:
                results.append(f"{prefix}{repr(item)}")

        _flatten(raw_dna)
        return tuple(sorted(set(results)))

    # ── 四源迁移工厂 ──

    @classmethod
    def from_legacy(cls, record: dict, source: MemorySource) -> "MemoryEntity":
        """从旧系统记录构造 MemoryEntity v2。"""
        content = record.get("content", record.get("text", record.get("label", "")))
        raw_dna = record.get("dna", record.get("tags", {}))
        dna = cls.normalize_dna(raw_dna)
        energy = record.get("energy", record.get("score", record.get("confidence", 0.5)))
        if isinstance(energy, (int, float)):
            energy = max(0.0, min(1.0, energy))
        else:
            energy = 0.5

        metadata = {}
        if "spatial" in record or "coord" in record:
            metadata["spatial"] = record.get("spatial", record.get("coord"))
        if "temporal" in record or "time_window" in record:
            metadata["temporal"] = record.get("temporal", record.get("time_window"))
        if "legacy_vec" in record:
            metadata["legacy_vec"] = record["legacy_vec"]

        return cls(
            id=record.get("id", f"{source}_{int(time.time())}"),
            dna=dna,
            content=content,
            energy=energy,
            pinned=record.get("pinned", False),
            source=source,
            created_at=record.get("created_at", time.time()),
            superseded_by=record.get("superseded_by"),
            metadata=metadata or None,
        )


__all__ = ["MemoryEntity", "MemorySource",
           "normalize_energy", "make_dna_strand", "validate_dna"]

# ── 辅助函数 (from_legacy 依赖) ──

def normalize_energy(raw_value: float, source: MemorySource) -> float:
    import math
    if source == "hindsight" or source == "dna_memory":
        return max(0.0, min(1.0, raw_value))
    elif source == "hub_3d":
        return 1.0 / (1.0 + math.exp(-raw_value / 3.0))
    elif source == "hermes":
        return min(1.0, math.log2(1 + max(0, raw_value)) / 10.0)
    return max(0.0, min(1.0, raw_value))

def make_dna_strand(*parts: str) -> tuple[str, ...]:
    """构造标准化DNA链。自动去重、排序、过滤空串。"""
    cleaned = tuple(sorted(set(p for p in parts if p and p.strip())))
    return cleaned

def validate_dna(dna: tuple[str, ...]) -> None:
    if not dna:
        return
    for item in dna:
        if ":" in item:
            raise ValueError(f"DNA item contains ':' separator: {item}")

