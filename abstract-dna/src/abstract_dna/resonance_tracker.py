"""共振路径追踪器 — 抽象DNA规则自生长实验

概念:
  每次查询命中抽象信号，记录查询词→信号的路径。
  当同一条路径命中足够多次（threshold=5），
  自动生成一条新的抽象规则。

使用:
  tracker = ResonanceTracker()
  tracker.record("凭证不对", {"action:auth", "status:error"})
  new_rules = tracker.evolve()
  # 如果 "凭证不对"→action:auth 出现5次以上，
  # 自动生成 {"pattern": "凭证不对", "signal": "action:auth", ...}
"""

import json, os, re, time
from collections import defaultdict, Counter

class ResonanceTracker:
    """追踪查询→信号的共振路径，高频路径自动生成为规则。"""

    def __init__(self, threshold: int = 5, lab_dir: str = None):
        self.threshold = threshold
        self._MIN_FRAG_LEN = 2
        self._MIN_UNIQUE_QUERIES = 3
        self.lab_dir = lab_dir or os.path.expanduser("~/strand-lab/abstract-dna")
        self.paths = defaultdict(lambda: defaultdict(int))  # {signal: {query_fragment: count}}
        self._load_state()

    def _state_path(self):
        return os.path.join(self.lab_dir, "results", "resonance_state.json")

    def _load_state(self):
        path = self._state_path()
        if os.path.exists(path):
            try:
                with open(path) as f:
                    data = json.load(f)
                raw = data.get("paths", {})
                for sig, frags in raw.items():
                    for frag, cnt in frags.items():
                        self.paths[sig][frag] = cnt
            except Exception:
                pass

    def _save_state(self):
        path = self._state_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        raw = {sig: dict(frags) for sig, frags in self.paths.items()}
        with open(path, "w") as f:
            json.dump({
                "version": 1,
                "threshold": self.threshold,
                "paths": raw,
                "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")
            }, f, indent=2, ensure_ascii=False)

    def record(self, query: str, signals: set):
        """记录一次查询命中了哪些抽象信号。
        
        从查询中提取关键词片段（2-4个中文字或英文词），
        关联到命中的信号。
        """
        # Extract meaningful fragments from query
        fragments = set()
        # Chinese fragments (2-4 chars)
        for m in re.finditer(r'[\u4e00-\u9fff]{2,4}', query):
            fragments.add(m.group())
        # English words (2+ chars)
        for m in re.finditer(r'[a-zA-Z]{2,}', query):
            fragments.add(m.group().lower())

        for sig in signals:
            for frag in fragments:
                self.paths[sig][frag] += 1

        self._save_state()


    # ── 质量门 ──
    # 高频停用词（永远不会生成规则）
    _STOP_WORDS = {
        "怎么", "什么", "为什么", "如何", "哪个", "这个", "那个",
        "可以", "没有", "不是", "就是", "还是", "或者", "如果",
        "然后", "而且", "但是", "因为", "所以", "虽然", "不过",
        "what", "how", "why", "which", "this", "that", "the",
        "and", "for", "with", "from", "been", "have", "has",
        "about", "into", "than", "then", "also", "very", "just",
    }
    # 最小规则质量要求
    _MIN_FRAG_LEN = 2        # 片段至少2个字符
    _MIN_UNIQUE_QUERIES = 3  # 至少来自3次不同查询（防同一句话刷屏）
    def evolve(self) -> list[dict]:
        """检查所有路径，高频的自动生成为规则。

        规则生成条件（必须全部满足）:
        1. 同一信号-片段对命中 >= threshold 次
        2. 片段长度 >= _MIN_FRAG_LEN
        3. 不是高频停用词
        4. 至少来自 _MIN_UNIQUE_QUERIES 次不同查询
        5. 该片段尚未被任何已有规则覆盖
        """
        # Load current rules to check for existing coverage
        rules = self._load_rules()
        existing_patterns = set()
        for r in rules:
            for pattern in r["pattern"].split("|"):
                existing_patterns.add(pattern.strip().lower())

        new_rules = []
        for sig, fragments in self.paths.items():
            for frag, count in fragments.items():
                # Gate 1: 阈值
                if count < self.threshold:
                    continue
                # Gate 2: 最小长度
                if len(frag) < self._MIN_FRAG_LEN:
                    continue
                # Gate 3: 停用词
                if frag.lower() in self._STOP_WORDS:
                    continue
                # Gate 4: 至少来自不同查询
                # (当前实现中 fragment 去重，所以 count 已经代表不同查询)
                if count < self._MIN_UNIQUE_QUERIES:
                    continue
                # Gate 5: 未覆盖
                if frag.lower() in existing_patterns:
                    # 但可以增强已有规则的命中权重
                    for r in rules:
                        if frag.lower() == r["pattern"].split("|")[0].strip().lower():
                            r["weight"] = min(r.get("weight", 0.3) + 0.05, 0.6)
                            break
                    continue

                new_rule = {
                    "pattern": re.escape(frag),
                    "signal": sig,
                    "weight": 0.3,
                    "auto_generated": True,
                    "hit_count": count,
                    "generated_at": time.strftime("%Y-%m-%d %H:%M:%S")
                }
                new_rules.append(new_rule)
                existing_patterns.add(frag.lower())

        return new_rules

    def _load_rules(self) -> list:
        # Load the latest rules file
        rules_dir = os.path.join(self.lab_dir, "rules")
        versions = sorted([f for f in os.listdir(rules_dir) if f.startswith("rules_v")])
        if not versions:
            return []
        latest = versions[-1]
        with open(os.path.join(rules_dir, latest)) as f:
            data = json.load(f)
        return data["rules"]

    def integrate_rules(self, new_rules: list[dict]) -> str:
        """将新规则合并到最新规则文件，保存为新版本。"""
        if not new_rules:
            return ""
        
        # Load latest
        rules_dir = os.path.join(self.lab_dir, "rules")
        versions = sorted([f for f in os.listdir(rules_dir) if f.startswith("rules_v")])
        latest = versions[-1]
        with open(os.path.join(rules_dir, latest)) as f:
            data = json.load(f)
        
        version = data["version"] + 1
        auto_count = sum(1 for r in new_rules if r.get("auto_generated"))
        manual_count = sum(1 for r in new_rules if not r.get("auto_generated"))
        
        data["version"] = version
        data["description"] = f"v{version}: 自动生长 {auto_count} 条规则"
        data["rules"].extend(new_rules)
        
        out_path = os.path.join(rules_dir, f"rules_v{version}.json")
        with open(out_path, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        return out_path

    def status(self) -> dict:
        """返回追踪器的状态摘要。"""
        total_paths = sum(len(frags) for frags in self.paths.values())
        total_hits = sum(c for frags in self.paths.values() for c in frags.values())
        hot_paths = sum(1 for frags in self.paths.values() 
                        for c in frags.values() if c >= self.threshold)
        
        return {
            "signals_tracked": len(self.paths),
            "unique_paths": total_paths,
            "total_hits": total_hits,
            "hot_paths_ready": hot_paths,
            "threshold": self.threshold
        }
