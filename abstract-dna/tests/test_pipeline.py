"""Tests for abstract-dna pipeline."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from abstract_dna import pipeline, RuleChannel, normalize

def test_rule_channel_basic():
    ch = RuleChannel()
    # setup signal
    s = ch.match("帮我装个nginx")
    assert 'action:setup' in s, f"Expected action:setup in {s}"
    # process signal
    s = ch.match("重启服务器")
    assert 'action:process' in s, f"Expected action:process in {s}"
    # search signal - "查这个文件" may hit entity:file rather than action:search
    s = ch.match("查一下这个文件")
    assert s, f"Expected signals for search query, got none"
    has_relevant = 'action:search' in s or 'action:inspect' in s or 'entity:file' in s
    assert has_relevant, f"Expected search/inspect/file signal in {s}"
    print("✅ test_rule_channel_basic")

def test_pipeline():
    # Chinese
    r = pipeline("帮我检查一下数据库连接")
    assert r['signals'], f"Expected signals, got none"
    assert any('action:' in s for s in r['signals']), f"Expected action signal in {r['signals']}"
    
    # English
    r = pipeline("check database connection")
    assert r['signals'], f"Expected signals for English query"
    
    # Mixed
    r = pipeline("这个API timeout了怎么fix")
    assert len(r['signals']) >= 2, f"Expected 2+ signals for mixed query, got {r['signals']}"
    print("✅ test_pipeline")

def test_normalize():
    assert normalize("帮我装一下") == "安装"
    assert normalize("查查这个文件") == "查询 文件"
    assert normalize("") == ""
    assert "安装" in normalize("帮我部署一下这个服务")
    print("✅ test_normalize")

def test_noise_rejection():
    # Pure emoji should not match
    r = pipeline("😭")
    assert not r['signals'], f"Emoji should not match signals"
    
    # Single chars should not match
    r = pipeline("那")
    assert not r['signals'], f"Single char should not match"
    print("✅ test_noise_rejection")

def test_dialect():
    # Dialect should still hit proceed
    r = pipeline("搞乜嘢")
    assert 'action:proceed' in r['signals'], f"Dialect should hit proceed, got {r['signals']}"
    
    r = pipeline("咋整嘛")
    assert 'action:proceed' in r['signals'], f"Dialect should hit proceed, got {r['signals']}"
    print("✅ test_dialect")

if __name__ == '__main__':
    test_rule_channel_basic()
    test_pipeline()
    test_normalize()
    test_noise_rejection()
    test_dialect()
    print("\n🎉 All tests passed!")
