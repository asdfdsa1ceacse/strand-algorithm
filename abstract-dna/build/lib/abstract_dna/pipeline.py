"""
抽象DNA双通道管线 (v1)
  
  规则表 (regex) → 语义信号 (精确分类, ~0.01ms)
  DNA共振 (坐标) → 实体召回 (模糊匹配, ~0.1ms)
  
  合并输出: {信号集 + 实体集}
"""

import sys, os, json, re, time
from collections import Counter

sys.path.insert(0, os.path.dirname(__file__))
from normalizer import normalize

LAB_DIR = os.path.dirname(os.path.abspath(__file__))

# ── 通道1: 规则表 (regex) ──
class RuleChannel:
    def __init__(self, rules_path=None):
        if rules_path is None:
            # Look for bundled data file relative to package
            pkg_dir = os.path.dirname(os.path.abspath(__file__))
            rules_path = os.path.join(pkg_dir, 'data', 'rules.json')
            if not os.path.exists(rules_path):
                # Fallback to old lab path
                rules_path = os.path.join(os.path.dirname(pkg_dir), 'rules', 'rules_v10.json')
        with open(rules_path, encoding='utf-8') as f:
            data = json.load(f)
        self.rules = data['rules']
        for r in self.rules:
            try:
                r['_compiled'] = re.compile(r['pattern'], re.IGNORECASE)
            except:
                r['_compiled'] = None
        self.timing = 0
    
    def match(self, text):
        signals = {}
        t0 = time.perf_counter()
        for r in self.rules:
            if r['_compiled'] is None:
                continue
            m = r['_compiled'].search(text)
            if m:
                sig = r['signal']
                weight = r.get('weight', 0.3)
                if sig not in signals or weight > signals[sig]:
                    signals[sig] = weight
        self.timing = time.perf_counter() - t0
        return signals

# ── 通道2: DNA坐标共振 ──
class DnaChannel:
    """
    轻量DNA坐标共振：
    - 字符级重叠 (char n-gram)
    - 子串包含
    - 加权打分
    """
    def __init__(self):
        # Load entity pool (strand_memory.json from hermès)
        pool_path = os.path.expanduser('~/.hermes/strand_memory.json')
        self.entities = []
        if os.path.exists(pool_path):
            with open(pool_path) as f:
                data = json.load(f)
            entities = data.get('entities', data.get('pool', {}).get('entities', []))
            if not entities:
                # Try as direct list
                entities = data if isinstance(data, list) else []
            
            for e in entities:
                if isinstance(e, dict):
                    text = e.get('text', e.get('content', ''))
                    eid = e.get('id', 'unknown')
                    domain = e.get('domain', '')
                    pinned = e.get('pinned', False)
                    energy = e.get('energy', 0.5)
                    self.entities.append({
                        'id': eid, 'text': text,
                        'domain': domain, 'pinned': pinned, 'energy': energy
                    })
        
        # Fallback: also load rules as virtual entities
        rules_path = os.path.join(LAB_DIR, 'rules', 'rules_v10.json')
        if os.path.exists(rules_path):
            with open(rules_path) as f:
                rdata = json.load(f)
            for r in rdata['rules']:
                self.entities.append({
                    'id': f"rule:{r['signal']}",
                    'text': r['pattern'].replace('|', ' '),
                    'domain': 'rule',
                    'pinned': False,
                    'energy': r.get('weight', 0.3)
                })
    
    def _char_overlap(self, a, b):
        """字符级重叠（中文单字+英文len>=2）"""
        def tokens(s):
            tokens = set()
            # Chinese single chars
            for ch in s:
                if '\u4e00' <= ch <= '\u9fff':
                    tokens.add(ch)
            # English words >= 2 chars
            for m in re.finditer(r'[a-zA-Z]{2,}', s):
                tokens.add(m.group().lower())
            return tokens
        ta = tokens(a)
        tb = tokens(b)
        if not ta or not tb:
            return 0
        overlap = len(ta & tb)
        return overlap / max(len(ta), len(tb))
    
    def _substr_overlap(self, a, b):
        """子串重叠：a中的子串是否出现在b中"""
        # Chinese 2-grams from a
        hits = 0
        for i in range(len(a) - 1):
            chunk = a[i:i+2]
            if '\u4e00' <= chunk[0] <= '\u9fff' and '\u4e00' <= chunk[1] <= '\u9fff':
                if chunk in b:
                    hits += 1
        # English words from a in b
        for m in re.finditer(r'[a-zA-Z]{2,}', a.lower()):
            if m.group() in b.lower():
                hits += 1
        return hits
    
    def match(self, text, top_k=5):
        t0 = time.perf_counter()
        results = []
        
        for ent in self.entities:
            etext = ent.get('text', '') or ent.get('content', '')
            if not etext:
                continue
            
            char_score = self._char_overlap(text, etext)
            substr_score = self._substr_overlap(text, etext)
            
            # Combined score
            score = char_score * 0.6 + min(substr_score * 0.2, 0.4)
            
            if score > 0.05:  # Threshold
                results.append({
                    'entity_id': ent['id'],
                    'entity_text': etext[:60],
                    'domain': ent.get('domain', ''),
                    'score': round(score, 3)
                })
        
        results.sort(key=lambda x: -x['score'])
        self.timing = time.perf_counter() - t0
        return results[:top_k]

# ── 进化记录器 (旁路) ──
_EVOLVER = None
_EVOLVER_ENABLED = True

def set_evolver(tracker):
    global _EVOLVER
    _EVOLVER = tracker

def get_evolver():
    global _EVOLVER
    if _EVOLVER is None and _EVOLVER_ENABLED:
        try:
            sys.path.insert(0, os.path.dirname(__file__))
            from resonance_tracker import ResonanceTracker
            _EVOLVER = ResonanceTracker(threshold=5, lab_dir=os.path.dirname(__file__))
        except ImportError:
            _EVOLVER = False
    return _EVOLVER if _EVOLVER else None

# ── 完整管线 ──
def pipeline(query, record_evolution=False):
    result = {
        'query': query,
        'normalized': '',
        'signals': {},
        'entities': [],
        'timing': {},
        'evolved': False
    }
    
    # Step 1: Normalize
    t0 = time.perf_counter()
    norm = normalize(query)
    result['normalized'] = norm
    result['timing']['normalize'] = round((time.perf_counter() - t0) * 1000, 2)
    
    # Step 2: Rule match
    rule_channel = RuleChannel()
    signals = rule_channel.match(norm)
    result['signals'] = dict(sorted(signals.items(), key=lambda x: -x[1]))
    result['timing']['rules'] = round(rule_channel.timing * 1000, 2)
    
    # Step 3: DNA resonance
    dna_channel = DnaChannel()
    entities = dna_channel.match(query, top_k=5)
    result['entities'] = entities
    result['timing']['dna'] = round(dna_channel.timing * 1000, 2)
    
    result['timing']['total'] = round(
        result['timing']['normalize'] + result['timing']['rules'] + result['timing']['dna'], 2
    )
    
    # Step 4 (旁路): 进化记录
    if record_evolution:
        evolver = get_evolver()
        if evolver:
            # 命中信号（规则表识别出了类型）→ 记录为"正确路径"
            if signals:
                evolver.record(norm, set(signals.keys()))
            
            # 规则未命中 → DNA兜住 → 记录DNA域作为线索信号
            if not signals and entities:
                domains_used = set()
                for e in entities:
                    d = e.get('domain', '')
                    if d and d not in ('rule', ''):
                        domains_used.add(f"entity:{d}")
                    # 也记录实体id中的信号线索
                    eid = e.get('entity_id', '')
                    if eid.startswith('rule:'):
                        domains_used.add(eid[5:])
                if domains_used:
                    evolver.record(norm, domains_used)
                else:
                    # 完全无域可记时，用最高分实体的前40字作为"信号"
                    if entities:
                        evolver.record(norm, {f"dna:{entities[0]['entity_text'][:20]}"})
            
            # 检查进化
            new_rules = evolver.evolve()
            if new_rules:
                result['evolved'] = True
                result['new_rules_count'] = len(new_rules)
                saved_path = evolver.integrate_rules(new_rules)
                result['new_rules_path'] = saved_path
    
    return result

def batch_eval(queries, sample_count=10):
    """Run pipeline on all queries and report"""
    rule_only_hits = 0
    dna_extra_hits = 0  # Queries where rule missed but DNA hit
    both_hits = 0
    all_miss = 0
    total_signals = 0
    
    # Track which signals come from rules vs DNA
    rule_signals = Counter()
    dna_domains = Counter()
    
    results = []
    t0 = time.perf_counter()
    
    for q in queries:
        r = pipeline(q)
        has_signal = bool(r['signals'])
        has_entity = bool(r['entities'])
        
        if has_signal:
            rule_only_hits += 1
            for sig in r['signals']:
                rule_signals[sig] += 1
            total_signals += len(r['signals'])
        elif has_entity:
            dna_extra_hits += 1
        else:
            all_miss += 1
        
        if has_signal and has_entity:
            both_hits += 1
        
        for e in r['entities']:
            dna_domains[e['domain']] += 1
        
        results.append(r)
    
    elapsed = time.perf_counter() - t0
    total = len(queries)
    
    print(f"双通道管线评估 — {total}条查询")
    print("=" * 60)
    print(f"""
规则表命中:       {rule_only_hits}/{total} ({rule_only_hits/total*100:.1f}%)
  └─ 其中同时有DNA匹配: {both_hits}
DNA额外兜底:     {dna_extra_hits}/{total} ({dna_extra_hits/total*100:.1f}%)  ← 规则未命中但DNA匹配到
全部未命中:      {all_miss}/{total} ({all_miss/total*100:.1f}%)
综合命中率:      {(rule_only_hits + dna_extra_hits)/total*100:.1f}%
平均信号/查询:   {total_signals/max(rule_only_hits,1):.2f}
总耗时:          {elapsed:.2f}s ({elapsed/total*1000:.1f}ms/查询)
""")
    
    # Show sample
    if sample_count > 0:
        print(f"── 采样 ({sample_count}) ──")
        for r in results[:sample_count]:
            has_sig = "🔵" if r['signals'] else "⚪"
            has_ent = "🟢" if r['entities'] else "⚪"
            sigs = ', '.join(r['signals'].keys()) if r['signals'] else '(无)'
            top_ent = r['entities'][0]['entity_text'] if r['entities'] else '(无)'
            top_score = r['entities'][0]['score'] if r['entities'] else 0
            print(f"  {has_sig}{has_ent} {r['query'][:45]}")
            print(f"       信号: {sigs}")
            print(f"       DNA: {top_ent} (评分:{top_score})")
            print(f"       耗时: {r['timing']['total']}ms")
            print()
    
    return results

if __name__ == '__main__':
    # Quick test
    test_queries = [
        "那开始吧",
        "啥时候弄",
        "那就搞",
        "然后呢",
        "好",
        "那这个怎么搞",
        "记忆存了吗",
        "备份一下这个配置",
        "gpu服务器多少钱",
        "帮我装个nginx",
        "为什么启动不了",
        "还行",
        "好嘞",
        "那就先这样",
        "看看那个",
    ]
    
    print("=" * 60)
    print("双通道管线 v1 — 快速测试")
    print("=" * 60)
    batch_eval(test_queries, sample_count=15)

