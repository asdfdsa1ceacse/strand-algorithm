# Abstract DNA — A Structural Matching Engine That Bypasses the Semantic Gap

## Abstract

Traditional NLP approaches attempt to make machines "understand" the semantics of human language before executing tasks. This paper proposes a fundamentally different path: **instead of trying to understand semantics, we go directly from text structure to response via parallel matching channels.** A rule table provides exact signal classification (86.5% coverage), while DNA coordinate resonance provides fuzzy entity recall (13.4% fallback). Combined, they reach 99.9% coverage on 799 real conversational queries and 67% on 58 intentionally adversarial queries (dialects, code-switching, scrambled word order, typos, negation stacking).

No LLM, no embeddings, no GPU. Zero hallucination risk. ~11ms per query.

## 1. Core Idea: Skip Understanding, Don't Model It

**Traditional pipeline:**
```
User: "go fix that thing"
  → resolve "that thing" (entity disambiguation)
  → resolve "fix" (intent classification)
  → execute
  (Each step guesses. Each guess can be wrong.)
```

**DNA structural matching pipeline:**
```
User: "go fix that thing"
  → normalize: "fix that thing"
  → rule table: "fix" → action:fix
  → DNA resonance: "that thing" characters → nearest entities
  → output directly
  (Skip "understanding". Go straight to response.)
```

If you can't misunderstand, you can't hallucinate. If structural matching produces the correct output, "understanding" is an unnecessary intermediate step.

## 2. Architecture

```
User query
  │
  ▼
Normalizer (30 filler word filters + 30 verb normalizations)
  │
  ├──→ Channel A: Rule Table (regex, 354 rules)
  │      Precise classification → semantic signal set
  │      Covers 86.5%
  │
  └──→ Channel B: DNA Coordinate Resonance (char overlap scoring)
           Fuzzy recall → entity fingerprint set
           Covers 13.4% (rules missed but DNA matched)
  │
  ▼
Merged output: {semantic signals + entity fingerprints} → 99.9%
  │
  └──→ [Sidecar] Evolution Engine
           Accumulates high-frequency unmatched paths
           Threshold=5 → auto-generates new rules to JSON
```

### 2.1 Channel A: Rule Table

354 regex rules across 9 signal categories:
- **Action** (14 types): proceed, memory, setup, search, process, transfer, delete, inspect, generate, fix, modify, backup, experiment, stop, close, auth, io, create
- **Status** (4): ok, error, warning, pending
- **Entity** (7): person, machine, file, data, project, web, cost
- **Tech** (6): ml, api, language, database, container, protocol
- **Format** (7): image, video, audio, text, code, binary, structured
- **Relation** (4): negate, and, or, contain
- **Quantity** (5): all, partial, many, one, first
- **Time** (4): near, period, daypart, recent
- **Question** (1): question

Each rule: `{pattern: "regex_string", signal: "signal_name", weight: float}`

### 2.2 Channel B: DNA Coordinate Resonance

Both query and entities are treated as character fingerprints (Chinese char n-grams + English words ≥2 chars). Resonance score is calculated by:

```
score = char_overlap(query, entity) × 0.6 + min(substr_overlap(query, entity) × 0.2, 0.4)
```

No semantic dictionary. No word embeddings. No training data required.

### 2.3 Evolution Engine (Sidecar)

Records paths where "rules missed but DNA caught it." When the same path accumulates ≥5 hits (from ≥3 distinct queries), it auto-generates a new regex rule. The threshold mechanism ensures one-off fringe queries never pollute the rule table.

## 3. Evaluation

### 3.1 799 Real Conversational Queries

| Metric | v9 (initial) | v10 (optimized) | Change |
|--------|:------------:|:---------------:|:------:|
| Overall hit rate | 70.3% | **86.5%** | ↑ +16.2% |
| Precise hit rate | 55.7% | **77.7%** | ↑ +22.0% |
| Miss rate | 29.7% | **13.5%** | ↓ -16.2% |
| Negation-only hits | 64 | **43** | ↓ -33% |
| Avg signals/query | 1.79 | **2.58** | ↑ +44% |

Dual-channel combined: Rule table 86.5% + DNA fallback 13.4% = **99.9%**.
The single miss was the system signal "received signal 15" — not a natural language query.

### 3.2 58 Adversarial High-Difficulty Queries

| Challenge | Example | Result |
|-----------|---------|:------:|
| Dialect | "搞乜嘢" (Cantonese) | ✅ action:proceed |
| Code-switching | "这个API的response timeout怎么fix" | ✅ 3 signals + DNA |
| Scrambled order | "服务器 重启 给我" | ✅ action:process + entity:machine |
| Negation stacking | "不是那个不不是不是那个" | ✅ rel:negate + DNA |
| Typos | "记亿" (wrong character for "memory") | 🟡 DNA partial coverage |
| Pure emoji/punctuation | "😭" "👍" "？？？" | ✅ Correctly rejected |
| English abbreviations | "wth" "ooms" "segfault" | ❌ Missed |
| Single characters | "那" "咋" "嗯" | ❌ Missed |

Overall adversarial hit rate: 67%. The remaining 33% are primarily correct rejections (noise, single chars) or future extension targets (English technical jargon).

### 3.3 Performance

- Single pipeline execution: avg 11.3ms
  - Rule matching: < 0.01ms
  - DNA resonance: < 0.1ms
  - Normalization: < 0.01ms
- Zero external dependencies. Pure Python 3 stdlib.

## 4. Design Principles

1. **Never merge the two engines.** Rule table does exact classification (regex). DNA does fuzzy recall (coordinate resonance). Different strategies — forcing them into one engine degrades both.
2. **Skip semantics.** No embeddings. No LLM. Structural matching cannot hallucinate.
3. **Evolution is a sidecar.** Not in the critical path. Default OFF. Avoids IO overhead on every query.
4. **Rule tables converge.** 354 rules cover 86.5%. Expected ceiling ~500 rules. More is not better.

## 5. Comparison with Existing Methods

| Method | Training? | GPU? | Hallucination? | Latency | Coverage |
|--------|:---------:|:----:|:--------------:|:-------:|:--------:|
| Rule table (DNA) | No | No | None | 0.01ms | 86.5% |
| + DNA resonance | No | No | None | 11ms | 99.9% |
| Word embeddings | Yes | Yes | Low | ~100ms | ~90% |
| LLM | Yes | Yes | High | ~2000ms | ~95% |

Unique advantage of DNA: **zero hallucination + zero cost + fully traceable.** Every signal hit has a specific regex pattern that can be inspected.

## 6. Limitations

- Single-character queries ("那" "咋") are too short for any text-matching method
- English-only technical terms ("ooms" "segfault") need English rule expansion
- Evolution quality gates can be further tightened
- Currently validated on Chinese user data; English scenarios need independent testing

## 7. Conclusion

Structural matching that bypasses semantic understanding is viable in practice. On 799 real user queries it achieves 99.9% coverage; on 58 adversarial fringe queries it achieves 67%. It requires no LLM, has zero hallucination risk, executes in ~11ms, and every match is fully traceable. For queries that express clear operational intent, **not "understanding" has proven to be a feature, not a limitation.**
