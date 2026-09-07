# -*- coding: utf-8 -*-
"""中文分词。jieba 在就用 jieba，不在就退到 n-gram，保证引擎永远能跑。"""
import re

_ASCII = re.compile(r"[A-Za-z][A-Za-z0-9+#./\-]{1,20}")
_CJK = re.compile(r"[一-龥]+")

try:
    import jieba
    jieba.setLogLevel(60)
    for w in ("知识库", "评测集", "意图识别", "检索策略", "召回率", "准确率", "badcase",
              "多轮对话", "策略产品", "用户增长", "大模型", "私有库", "公库", "私库",
              "知识生产", "指标口径", "归因", "冷启动", "留存率", "转化率", "渗透率"):
        jieba.add_word(w)
    _HAS_JIEBA = True
except Exception:                                    # pragma: no cover
    _HAS_JIEBA = False


def _ngrams(s: str, lo=2, hi=4) -> list[str]:
    out = []
    for n in range(lo, hi + 1):
        out += [s[i:i + n] for i in range(len(s) - n + 1)]
    return out


def cut(text: str) -> list[str]:
    """返回小写词元。英文按整词，中文按 jieba（或 n-gram 兜底）。"""
    toks: list[str] = []
    for m in _ASCII.finditer(text):
        toks.append(m.group(0).lower())
    for m in _CJK.finditer(text):
        seg = m.group(0)
        if _HAS_JIEBA:
            toks += [w for w in jieba.cut(seg) if len(w) >= 2]
        else:
            toks += _ngrams(seg)
    return toks


STOP = set("""
的 了 和 与 及 或 在 为 对 是 有 能 会 等 并 且 以 从 到 将 把 被 使 让 就 都 也 还
我们 你 你们 他们 相关 具备 良好 熟悉 了解 负责 参与 进行 完成 通过 基于 以及 其他
岗位 职责 要求 工作 内容 描述 优先 加分 经验 经历 能力 以上 至少 熟练 精通 掌握 应用
""".split())


def keywords(text: str, limit: int = 10) -> list[str]:
    """抽可用于匹配的关键词：去停用词、去纯数字、保序去重。"""
    out, seen = [], set()
    for t in cut(text):
        if t in STOP or len(t) < 2 or t.isdigit():
            continue
        if t in seen:
            continue
        seen.add(t)
        out.append(t)
    return out[:limit]
