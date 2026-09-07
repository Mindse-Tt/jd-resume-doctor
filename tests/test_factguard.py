# -*- coding: utf-8 -*-
"""红线测试。FactGuard 是"不替用户编造经历"这条产品红线的唯一执行点，
这个文件必须全绿，任何改动都不许放宽它。"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.factguard import check
from core.models import FactLedger, Suggestion


@pytest.fixture
def facts():
    return FactLedger(
        numbers=["30%", "80%", "3", "800", "12"],
        entities=["RAG", "Agent", "Python", "SQL"],
    )


def sug(after, before="原句：负责检索策略优化", state="A"):
    return Suggestion(bullet_id="E-01", state=state, before=before,
                      after=after, why="测试")


def test_放行_只用台账里的数字(facts):
    s = check(sug("重构检索策略，Top1 命中率由 30% 提升至 80%"), facts)
    assert s.guard_passed and s.state == "A"


def test_拦截_凭空捏造的数字(facts):
    s = check(sug("重构检索策略，命中率提升至 95%，覆盖 500 万用户"), facts)
    assert not s.guard_passed
    assert s.state == "C"                       # 必须降级，不能静默通过
    assert "95%" in s.guard_note or "500" in s.guard_note
    assert s.question                            # 必须给出追问


def test_拦截_凭空捏造的专有名词(facts):
    s = check(sug("基于 Elasticsearch 与 Milvus 重构检索链路"), facts)
    assert not s.guard_passed and s.state == "C"


def test_放行_占位符不算捏造(facts):
    s = check(sug("重构检索策略，Top1 命中率由 [[待确认:基线]] 提升至 [[待确认:结果]]"), facts)
    assert s.guard_passed


def test_放行_中文占位符(facts):
    s = check(sug("知识覆盖率【待填：口径 + 数字】"), facts)
    assert s.guard_passed


def test_放行_原句里本来就有的内容(facts):
    s = check(sug("优化 Milvus 检索链路", before="负责 Milvus 检索链路"), facts)
    assert s.guard_passed


def test_B态结构重组永远放行(facts):
    s = check(sug("任何内容 999% 都不检查", state="B"), facts)
    assert s.guard_passed


def test_用户补充的数字视为可信(facts):
    facts.user_supplied.append("92%")
    s = check(sug("人工抽检通过率 92%"), facts)
    assert s.guard_passed


def test_单位写法不同不误伤(facts):
    s = check(sug("提升 30 个百分点"), facts)   # 台账有 "30%"
    assert s.guard_passed
