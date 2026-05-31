"""
strand-regulate — 独立安全护栏（意图碰撞引擎）

在执行动作前，检查意图是否与预设原则（铁律）冲突。
每条原则包含 DNA 匹配模式，碰撞则阻止或警告。

独立可用，不依赖其他包。

用法:
    from strand_regulate import Regulator
    reg = Regulator([
        {"id": "no_delete", "description": "禁止删除生产数据",
         "keywords": ["delete", "remove", "drop", "删除", "清除"],
         "level": "block"},
    ])
    result = reg.check("我想删除这个文件")
    # → RegulateResult(blocked=True, reason="触犯: no_delete")
"""

from __future__ import annotations
from typing import Optional
from dataclasses import dataclass, field


@dataclass
class RegulateResult:
    blocked: bool = False
    hits: list[dict] = field(default_factory=list)
    action: str = ""


class Regulator:
    """意图碰撞规制引擎。"""

    def __init__(self, principles: list[dict]):
        """
        principles = [
            {"id": "...", "description": "...",
             "keywords": [...], "level": "block"|"warn"},
        ]
        """
        self.principles = principles

    def check(self, action_text: str) -> RegulateResult:
        """检查一个行动意图是否违反铁律。"""
        t = action_text.lower()
        hits = []
        for p in self.principles:
            for kw in p.get("keywords", []):
                if kw.lower() in t:
                    hits.append({
                        "principle": p["id"],
                        "description": p.get("description", ""),
                        "keyword": kw,
                        "level": p.get("level", "warn"),
                    })
                    break  # 一条铁律只记一次
        blocked = any(h["level"] == "block" for h in hits)
        return RegulateResult(
            blocked=blocked, hits=hits,
            action="block" if blocked else "pass",
        )

    def list_principles(self) -> list[dict]:
        return [
            {"id": p["id"], "description": p.get("description", ""),
             "level": p.get("level", "warn"), "keywords": p.get("keywords", [])}
            for p in self.principles
        ]

    def add_principle(self, principle: dict):
        self.principles.append(principle)


def demo_principles() -> list[dict]:
    """内置演示铁律。"""
    return [
        {"id": "no_delete", "description": "禁止删除生产数据/代码",
         "keywords": ["delete", "remove", "drop", "rm ", "删除", "清除"],
         "level": "block"},
        {"id": "no_destroy", "description": "禁止破坏基础设施",
         "keywords": ["destroy", "shutdown", "停服", "关机", "重启"],
         "level": "block"},
        {"id": "confirm_cost", "description": "高成本操作需确认",
         "keywords": ["gpu", "deploy", "batch", "大规模", "所有"],
         "level": "warn"},
    ]


__all__ = ["Regulator", "RegulateResult", "demo_principles"]

if __name__ == "__main__":
    reg = Regulator(demo_principles())
    tests = ["帮我删除服务", "查看日志", "部署到生产环境", "清空数据库"]
    for t in tests:
        r = reg.check(t)
        status = "🚫" if r.blocked else "⚠️" if r.hits else "✅"
        print(f"  {t:20s} → {status} (hits: {len(r.hits)})")
