# -*- coding: utf-8 -*-
"""岗位能力模型的判定逻辑测试。

这套逻辑最容易出的两类错：
  1. 判据串台——简历里任何一处的"因为"让所有维度都显得有论述
  2. 证据错配——引文和维度对不上号
两类都有专门的测试兜住。
"""
import os
import sys

import pytest
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from core import profile, structure

LOCKE = os.path.join(ROOT, "tests", "cases", "A_真实强简历.md")
BLANK = os.path.join(ROOT, "tests", "cases", "H_无AI内容.md")


@pytest.fixture(scope="module")
def lex():
    return yaml.safe_load(open(f"{ROOT}/kb/lexicon.yaml", encoding="utf-8"))


def parse(path, lex):
    if not os.path.exists(path):
        pytest.skip("样例简历不在这台机器上")
    return structure.parse(path, lex)


def test_模型能加载并且维度齐全():
    prof = profile.load("ai_pm")
    assert len(prof["dimensions"]) >= 8
    assert "ai_pm" in profile.available()


def test_不存在的岗位给出可读报错():
    with pytest.raises(FileNotFoundError) as e:
        profile.load("不存在的岗位")
    assert "可用" in str(e.value)


def test_有AI内容的简历显著高于无AI内容的(lex):
    ai, _ = profile.evaluate(parse(LOCKE, lex), "ai_pm")
    blank, _ = profile.evaluate(parse(BLANK, lex), "ai_pm")
    assert ai["score"] > blank["score"] + 40


def test_无AI内容的简历不该拿到强证据(lex):
    _, dims = profile.evaluate(parse(BLANK, lex), "ai_pm")
    assert all(d.level in ("L0", "L1") for d in dims)


def test_判据不串台_证据必须命中定义性信号(lex):
    """每个维度的引文必须真的命中该维度的第一个信号组。"""
    _, dims = profile.evaluate(parse(LOCKE, lex), "ai_pm")
    prof = profile.load("ai_pm")
    by_id = {d["id"]: d for d in prof["dimensions"]}
    for d in dims:
        if not d.quote:
            continue
        core = by_id[d.id]["signals"][:1]
        assert profile._match_count(core, d.quote) > 0, \
            f"{d.name} 的引文没有命中定义性信号：{d.quote[:40]}"


def test_L3必须有多条证据(lex):
    _, dims = profile.evaluate(parse(LOCKE, lex), "ai_pm")
    for d in dims:
        if d.level == "L3":
            assert len(d.evidence) >= 2, f"{d.name} 判了 L3 但只有 {len(d.evidence)} 条证据"


def test_缺口会翻译成问题条目(lex):
    _, dims = profile.evaluate(parse(LOCKE, lex), "ai_pm")
    kb = {}
    issues = profile.profile_issues(dims, kb)
    assert issues
    for i in issues:
        assert i.id.startswith("AIPM-")
        assert i.interviewer_view.startswith("面试官会问")
    assert all(i.severity in ("important", "suggestion") for i in issues)


def test_分数随强证据数量单调(lex):
    """L3 越多分越高——这是模型成立的基本要求。"""
    s, dims = profile.evaluate(parse(LOCKE, lex), "ai_pm")
    manual = sum(d.weight * profile.LEVEL_SCORE[d.level] for d in dims)
    assert abs(manual * 100 - s["score"]) < 0.15
