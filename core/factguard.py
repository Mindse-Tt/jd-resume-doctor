# -*- coding: utf-8 -*-
"""红线执行点：改写句里不许出现简历中不存在的事实。

这是纯程序校验，不依赖模型自觉——prompt 里写"请不要编造"是没有约束力的。
"""
import re

from .models import FactLedger, Suggestion

NUM = re.compile(r"\d+(?:\.\d+)?\s*(?:%|pp|万|亿|千|人|次|天|小时|分钟|秒|倍|条|个|元)?")
PLACEHOLDER = re.compile(r"\[\[[^\]]+\]\]|【[^】]*待[^】]*】|【待填[^】]*】")
ENTITY = re.compile(r"[A-Za-z][A-Za-z0-9+#./\-]{2,24}")

# 通用技术/指标词不算专有名词——它们是行话，不是简历里的事实
COMMON = {
    "ai", "llm", "rag", "api", "sql", "ui", "ux", "qa", "id", "ok", "pm", "prd",
    "mvp", "sop", "sla", "kpi", "okr", "roi", "roas", "cac", "ctr", "cvr", "gmv",
    "dau", "mau", "wau", "arr", "ltv", "ab", "a/b", "abtest", "top", "topk",
    "saas", "b2b", "b2c", "toc", "tob", "crud", "http", "json", "csv", "excel",
    "word", "ppt", "pdf", "demo", "app", "web", "sdk", "cli", "gpu", "cpu",
    "agent", "prompt", "token", "embedding", "rerank", "badcase", "workflow",
    "skill", "planner", "tool", "tools", "context", "memory", "tts", "asr",
}


def _is_proper_noun(tok: str) -> bool:
    """只把"像产品/公司名"的词当专有名词。
    含数字的多是指标简写（Top1 / P95 / 5v5），不该拦。"""
    if len(tok) < 4 or tok.lower() in COMMON:
        return False
    if any(c.isdigit() for c in tok):
        return False
    return True


def _strip_placeholders(text: str) -> str:
    return PLACEHOLDER.sub(" ", text)


def check(s: Suggestion, facts: FactLedger) -> Suggestion:
    """校验一条改写建议。不通过则降级为 C 态（待确认）。"""
    if s.state == "B":                      # 结构重组不改字，天然安全
        return s

    body = _strip_placeholders(s.after)
    bad_nums, bad_ents = [], []

    for m in NUM.finditer(body):
        tok = m.group(0).strip()
        if not re.search(r"\d", tok):
            continue
        if facts.allows_number(tok):
            continue
        # 数字本体在台账里（只是单位写法不同）也放行
        digits = re.match(r"\d+(?:\.\d+)?", tok).group(0)
        if any(n.startswith(digits) for n in facts.numbers + facts.user_supplied):
            continue
        if tok in s.before:                 # 原句里本来就有
            continue
        bad_nums.append(tok)

    known = {e.lower() for e in facts.entities}
    for m in ENTITY.finditer(body):
        tok = m.group(0)
        if tok.lower() in known or tok in s.before or not _is_proper_noun(tok):
            continue
        bad_ents.append(tok)

    if bad_nums or bad_ents:
        notes = []
        if bad_nums:
            notes.append("凭空出现的数字：" + "、".join(sorted(set(bad_nums))[:6]))
        if bad_ents:
            notes.append("凭空出现的专有名词：" + "、".join(sorted(set(bad_ents))[:6]))
        s.guard_passed = False
        s.guard_note = "；".join(notes)
        s.state = "C"
        if not s.question:
            s.question = "上面这句改写引入了简历里没有的信息，请确认真实数值/名称后再采用。"
    return s


def check_all(suggestions: list[Suggestion], facts: FactLedger) -> list[Suggestion]:
    return [check(s, facts) for s in suggestions]
