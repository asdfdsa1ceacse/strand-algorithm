"""
strand-immune — 独立学习器（分歧驱动免疫系统）

当匹配引擎做出错误匹配时，用户反馈会触发分歧记录。
免疫系统自动计算差集、写入 staging 区、按阈值 promote 为抗体，
并通过差异化半衰期衰减淘汰过时知识。

零标注数据，纯从错误中学习。

用法:
    from strand_immune import ImmuneSystem
    imm = ImmuneSystem()
    imm.record_miss("帮我部署系统", "analyst", "devops")
    # → 差集: {帮我, 部署系统} - {analyst的DNA词} = {部署}
    imm.promote(dry_run=True)  # 查看待 promote 的抗体
    imm.decay()                  # 衰减老化抗体
"""

from __future__ import annotations
import json, os, time, fcntl
from typing import Optional


class ImmuneSystem:
    """分歧驱动免疫系统。"""

    def __init__(self, storage_path: str = ""):
        self.staging: list[dict] = []
        self.antibodies: dict[str, list[dict]] = {}
        self.path = storage_path or os.path.expanduser(
            "~/.cache/strand_immune.json"
        )
        self._load()

    # ── 数据模型 ──

    @property
    def staging_count(self) -> int:
        return len(self.staging)

    @property
    def antibody_count(self) -> int:
        return sum(len(v) for v in self.antibodies.values())

    # ── 核心 API ──

    def record_miss(self, query: str, wrong_entity: str, correct_entity: str,
                    wrong_dna: Optional[dict] = None,
                    correct_dna: Optional[dict] = None):
        """记录一次匹配分歧。自动计算差集候选词。"""
        q_words = self._tokenize(query)
        wrong_words = set(
            w for vals in (wrong_dna or {}).values() for w in vals
        )
        diff = q_words - wrong_words
        # 排除正确实体的正链词（防止自己打自己）
        if correct_dna:
            right_words = set(
                w for vals in correct_dna.values() for w in vals
            )
            diff -= right_words
        for word in diff:
            self.staging.append({
                "word": word, "wrong_entity": wrong_entity,
                "correct_entity": correct_entity,
                "count": 1, "added": time.time(),
            })
        self._merge_staging()
        self._save()

    def promote(self, threshold: int = 3,
                dry_run: bool = False) -> list[dict]:
        """将达到阈值的 staging 候选 promote 为抗体。"""
        ready = []
        remaining = []
        for item in self.staging:
            if item["count"] >= threshold:
                entity = item["wrong_entity"]
                if entity not in self.antibodies:
                    self.antibodies[entity] = []
                self.antibodies[entity].append({
                    "word": item["word"],
                    "origin": "auto_grown",
                    "added": time.strftime(
                        "%Y-%m-%d", time.localtime()
                    ),
                })
                ready.append(item)
            else:
                remaining.append(item)
        if not dry_run:
            self.staging = remaining
            self._save()
        return ready

    def decay(self, migration_hl: int = 14, grown_hl: int = 30):
        """按物种半衰期衰减抗体。"""
        now = time.time()
        for entity, entries in list(self.antibodies.items()):
            alive = []
            for entry in entries:
                origin = entry.get("origin", "auto_grown")
                hl = migration_hl if origin == "migration" else grown_hl
                added = entry.get("added", "")
                age_days = (now - time.mktime(
                    time.strptime(added, "%Y-%m-%d")
                )) / 86400 if added else 0
                if age_days < hl:
                    alive.append(entry)
            if alive:
                self.antibodies[entity] = alive
            else:
                del self.antibodies[entity]
        self._save()

    # ── 内部 ──

    def _tokenize(self, text: str) -> set[str]:
        import re
        # 对中文分词（按 2 字滑动窗口），非英文词汇按单字拆分
        tokens = set()
        for w in re.findall(r"[a-zA-Z0-9_\u4e00-\u9fff]+", text.lower()):
            if re.match(r"^[\u4e00-\u9fff]+$", w):
                # 中文：按 2 字滑动窗口
                for i in range(len(w) - 1):
                    tokens.add(w[i:i+2])
            elif len(w) >= 2:
                tokens.add(w)
        return tokens

    def _merge_staging(self):
        seen: dict = {}
        for item in self.staging:
            key = (item["word"], item["wrong_entity"])
            if key in seen:
                seen[key]["count"] += 1
            else:
                seen[key] = item
        self.staging = list(seen.values())

    def _load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path) as f:
                    data = json.load(f)
                self.staging = data.get("staging", [])
                self.antibodies = data.get("antibodies", {})
            except (json.JSONDecodeError, OSError):
                pass

    def _save(self):
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "w") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            json.dump({
                "staging": self.staging,
                "antibodies": self.antibodies,
            }, f, ensure_ascii=False, indent=2)
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)


__all__ = ["ImmuneSystem"]

if __name__ == "__main__":
    imm = ImmuneSystem("/tmp/test_immune.json")
    imm.record_miss("帮我部署系统", "analyst", "devops")
    imm.record_miss("紧急部署服务器", "analyst", "devops")
    imm.record_miss("快速部署", "analyst", "devops")
    ready = imm.promote(dry_run=True)
    print(f"staging: {imm.staging_count}, promote 候选: {len(ready)}, 抗体: {imm.antibody_count}")
