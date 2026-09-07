# -*- coding: utf-8 -*-
"""对抗案例回归。

这些案例是专门用来骗模型的，每一条都对应一次真实发现的漏洞：
  D 术语堆砌   —— v0.1 时它拿 48.4 分，几乎等于一份真实强简历（49.8）
  E 有实质无术语 —— v0.1 时它拿 1.1 分，被判"不像 AI 产品岗简历"
  G 消融      —— 删掉全部因果论述后应该明显掉分
任何改动导致这些案例回到旧行为，都是回归。
"""
import os
import sys

import pytest
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from core import profile, structure

CASES = os.path.join(ROOT, "tests", "cases")


@pytest.fixture(scope="module")
def lex():
    return yaml.safe_load(open(f"{ROOT}/kb/lexicon.yaml", encoding="utf-8"))


def run(name, lex):
    path = os.path.join(CASES, name)
    if not os.path.exists(path):
        pytest.skip(f"缺少案例 {name}")
    return profile.evaluate(structure.parse(path, lex), "ai_pm")


def test_术语堆砌必须被识破(lex):
    s, _ = run("D_术语堆砌.md", lex)
    assert s["疑似术语堆砌"], "堆砌型简历没有被标记"
    assert s["置信度"] == "低"
    assert s["score"] < 30, f"堆砌型拿了 {s['score']} 分，太高"


def test_堆砌型必须显著低于真实简历(lex):
    stuff, _ = run("D_术语堆砌.md", lex)
    real, _ = run("A_真实强简历.md", lex)
    assert real["score"] > stuff["score"] + 15, \
        f"真实简历 {real['score']} vs 堆砌 {stuff['score']}，区分度不足"


def test_真实简历不该被误判为堆砌(lex):
    for name in ("A_真实强简历.md", "G_消融_删因果论述.md"):
        s, _ = run(name, lex)
        assert not s["疑似术语堆砌"], f"{name} 被误判为术语堆砌"


def test_无术语的简历必须标记为规则层判不了(lex):
    """大白话写的简历规则层召回不到，分数不能当结论。"""
    s, _ = run("E_有实质无术语.md", lex)
    assert s["需要语义层重判"], "无行话简历没有触发语义层重判标记"
    assert s["置信度"] == "低"


def test_删掉因果论述后应该掉分(lex):
    full, _ = run("A_真实强简历.md", lex)
    ablated, _ = run("G_消融_删因果论述.md", lex)
    assert ablated["score"] < full["score"], \
        f"消融版 {ablated['score']} 没有低于原版 {full['score']}"


def test_注水型不该拿高分(lex):
    s, _ = run("F_注水型.md", lex)
    assert s["score"] < 25, f"注水型拿了 {s['score']} 分"


def test_实质指标与行话量分开度量(lex):
    """堆砌型行话高具体性低，真实简历两者都高——必须能分开。"""
    stuff, _ = run("D_术语堆砌.md", lex)
    real, _ = run("A_真实强简历.md", lex)
    assert stuff["substance"]["行话密度"] > real["substance"]["行话密度"]
    assert stuff["substance"]["具体性"] < real["substance"]["具体性"]
