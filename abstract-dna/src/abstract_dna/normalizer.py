"""查询归一化层 — 编译链反向段

概念:
  用户输入先过归一化，再进入抽象DNA匹配。
  归一化做三件事:
  1. 砍虚词: 帮我/一下/这个/那个/了/的/吗
  2. 动词归一: 装→安装, 搞→做, 查→查询
  3. 名词标准化: 不碰（保留原文让DNA自己共振）

用法:
  from normalizer import normalize
  query = "帮我装一下这个数据库"
  core = normalize(query)
  # → "安装 数据库"
"""

import re

# 虚词过滤（按长度降序，避免短词误杀）
_FILLER_WORDS = sorted([
    "帮我把", "帮我", "能帮我", "能不能", "可不可以",
    "一下", "一下下", "一会儿",
    "这个", "那个", "哪个", "这些", "那些",
    "怎么", "什么", "为什么", "如何",
    "请问", "我想", "我要", "我",
    "了", "的", "吗", "嘛", "呢", "吧", "啊", "哦", "嗯",
    "哈", "呗", "了哟", "哟",
    "please", "could you", "would you", "can you",
    "i want", "i need", "i would like", "i'd like",
], key=len, reverse=True)

# 动词归一表：方言/变体 → 标准形式
_VERB_NORMALIZE = {
    # 安装族
    "装": "安装",
    "装个": "安装",
    "装一": "安装",
    "安装一": "安装",
    "搭建": "安装",
    "搭个": "安装",
    "部署": "安装",
    "部署一": "安装",
    "配置": "安装",
    "编译": "安装",
    "编译一": "安装",
    "setup": "install",
    
    # 修改族
    "改": "修改",
    "改一": "修改",
    "改动": "修改",
    "变更": "修改",
    "编辑": "修改",
    "更新": "修改",
    "调一": "修改",
    "调整": "修改",
    
    # 搜索族
    "搜": "搜索",
    "搜一": "搜索",
    "找": "搜索",
    "找一": "搜索",
    "找找": "搜索",
    "查": "查询",
    "查一": "查询",
    "查查": "查询",
    "检索": "查询",
    "搜搜": "搜索",
    
    # 删除族
    "删": "删除",
    "删掉": "删除",
    "清": "清理",
    "清一": "清理",
    "清除": "清理",
    "清理一": "清理",
    
    # 传递族
    "传": "上传",
    "上传一": "上传",
    "下载一": "下载",
    "推": "推送",
    "拉": "拉取",
    "提交一": "提交",
    "发布一": "发布",
    "同步一": "同步",
    
    # 检查族
    "看看": "检查",
    "看一": "检查",
    "检测": "检查",
    "验证": "检查",
    "验一": "检查",
}

# 名词类标记（用于分类，实际不修改原文）
_NOUN_CATEGORIES = {
    "服务器": "machine", "机器": "machine", "主机": "machine",
    "数据库": "database", "mysql": "database", "redis": "database",
    "接口": "api", "api": "api", "endpoint": "api",
    "代码": "code", "源码": "code", "源": "code",
    "图片": "image", "头像": "image",
    "日志": "log", "记录": "record",
    "文件": "file", "文档": "file",
    "缓存": "cache", "临时文件": "cache",
    "数据": "data", "资料": "data",
    "用户": "user", "账号": "user",
    "密钥": "key", "token": "key", "凭证": "key",
    "配置": "config", "配置文件": "config",
    "密码": "password", "权限": "permission",
    "容器": "container", "镜像": "container", "docker": "container",
}


def normalize(query: str) -> str:
    """归一化用户查询：砍虚词 → 动词归一 → 返回核心意图。
    
    保留名词原文（让DNA自己共振）。
    输出适合送入抽象DNA匹配层。
    """
    if not query:
        return ""
    
    text = query.strip()
    original = text
    
    # Step 1: 砍虚词
    for filler in _FILLER_WORDS:
        text = text.replace(filler, " ")
    
    # Step 2: 压缩多余空格
    text = re.sub(r'\s+', ' ', text).strip()
    
    # Step 3: 动词归一（从长到短匹配）
    # Step 3: 动词归一（从长到短匹配，避免子串误伤）
    # 只在独立词上做替换，不替换已归一化的词
    sorted_verbs = sorted(_VERB_NORMALIZE.keys(), key=len, reverse=True)
    words = text.split()
    new_words = []
    for w in words:
        matched = False
        for variant, standard in [(v, _VERB_NORMALIZE[v]) for v in sorted_verbs]:
            if w == variant or w.startswith(variant):
                # 如果已经以标准形式开头，跳过
                if w.startswith(standard):
                    new_words.append(w)
                    matched = True
                    break
                # 替换变体为标准形式
                remaining = w[len(variant):]
                new_words.append(standard + remaining)
                matched = True
                break
        if not matched:
            new_words.append(w)
    text = " ".join(new_words)
    
    # Step 4: 再次压缩空格
    text = re.sub(r'\s+', ' ', text).strip()
    
    # Step 5: 砍尾词（"用"、"吧"、"哈"结尾）
    text = re.sub(r'(用|哈|吧|吗|呢|嘛|呗|哟)\s*$', '', text).strip()
    
    # If normalization produced nothing useful, return original
    if not text or len(text) < 2:
        return original
    
    return text


def extract_nouns(text: str) -> list[tuple[str, str]]:
    """从文本中提取名词及分类。
    
    返回: [(名词, 分类), ...]
    """
    results = []
    for word, category in _NOUN_CATEGORIES.items():
        if word in text:
            results.append((word, category))
    return results


def diagnostic(query: str) -> dict:
    """返回归一化全流程的诊断信息。"""
    original = query
    normalized = normalize(query)
    nouns = extract_nouns(normalized)
    
    return {
        "original": original,
        "normalized": normalized,
        "nouns": nouns,
        "filler_removed": original != normalized.replace("安装", "装").replace("搜索", "搜"),
        "verbs_found": [v for v in _VERB_NORMALIZE if v in original],
    }
