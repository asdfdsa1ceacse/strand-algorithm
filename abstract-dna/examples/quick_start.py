"""Quick start examples for abstract-dna."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from abstract_dna import pipeline, RuleChannel, normalize

# Example 1: Rule table classification
print("=== Example 1: Rule Table ===")
ch = RuleChannel()
queries = [
    "帮我装个nginx",
    "重启服务器",
    "查一下这个文件",
    "删除那个配置",
    "API timeout怎么fix",
]
for q in queries:
    signals = ch.match(q)
    print(f"  {q:<30s} → {', '.join(signals.keys())}")

# Example 2: Full pipeline
print("\n=== Example 2: Full Pipeline ===")
results = [
    pipeline("帮我检查一下数据库连接"),
    pipeline("今天那个deploy怎么样了"),
    pipeline("备份一下配置"),
]
for r in results:
    print(f"  Q: {r['query'][:35]}")
    print(f"  信号: {', '.join(r['signals'].keys())}")
    print()

# Example 3: Normalizer
print("=== Example 3: Normalizer ===")
examples = [
    "帮我装一下这个数据库",
    "查查这个文件在哪里",
    "能不能帮我重启一下服务",
    "请帮我部署一下新版本",
]
for q in examples:
    print(f"  {q:<30s} → {normalize(q)}")
