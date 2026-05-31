"""
strand-router — 独立联想引擎（跨域图路由）

给定一个匹配实体，从图谱中 BFS 展开 K 跳关联。
发现"语义不同但结构相同"的跨域关联。

不依赖 embedding，纯图遍历，零 token 消耗。

用法:
    from strand_router import Router
    r = Router()
    r.add_edge("devops", "cloud", relation="depends")
    result = r.route("devops", hops=2)
    # → [["devops", "cloud"], ...]
"""

from __future__ import annotations
from typing import Any


class Router:
    """跨域图路由引擎，BFS 展开。"""

    def __init__(self):
        self.graph: dict[str, list[dict[str, Any]]] = {}

    def add_edge(self, source: str, target: str, **attrs):
        """添加一条无向边。"""
        self.graph.setdefault(source, []).append({
            "name": target, **attrs
        })
        self.graph.setdefault(target, []).append({
            "name": source, **attrs
        })

    def add_edges_from(self, edges: list[tuple[str, str, dict]]):
        """批量添加边。"""
        for src, tgt, attrs in edges:
            self.add_edge(src, tgt, **attrs)

    def route(self, start: str, hops: int = 2,
              max_paths: int = 20) -> list[list[str]]:
        """BFS 展开，返回所有不超过 K 跳的路径。"""
        if start not in self.graph:
            return []
        paths = [[{"name": start, "depth": 0}]]
        results: list[list[str]] = []
        visited = {start}
        while paths:
            path = paths.pop(0)
            if len(path) > 1:
                results.append([n["name"] for n in path])
            if len(path) >= hops + 1 or len(results) >= max_paths:
                continue
            last = path[-1]
            for neighbor in self.graph.get(last["name"], []):
                if neighbor["name"] not in visited:
                    visited.add(neighbor["name"])
                    paths.append(path + [{
                        "name": neighbor["name"],
                        "depth": last["depth"] + 1,
                    }])
        return results

    def neighbors(self, node: str) -> list[str]:
        """直接邻居。"""
        return [
            n["name"] for n in self.graph.get(node, [])
        ]

    def node_count(self) -> int:
        return len(self.graph)

    def edge_count(self) -> int:
        return sum(len(v) for v in self.graph.values()) // 2


__all__ = ["Router"]

if __name__ == "__main__":
    r = Router()
    r.add_edges_from([
        ("devops", "cloud", {"relation": "deploy_target"}),
        ("devops", "docker", {"relation": "tool"}),
        ("docker", "kubernetes", {"relation": "orchestrate"}),
        ("kubernetes", "cloud", {"relation": "platform"}),
        ("cloud", "monitoring", {"relation": "ops"}),
    ])
    print(f"图: {r.node_count()} 节点, {r.edge_count()} 边")
    print(f"devops → {r.neighbors('devops')}")
    print(f"BFS 2跳: {r.route('devops', hops=2)}")
