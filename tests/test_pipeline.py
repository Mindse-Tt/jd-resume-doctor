# -*- coding: utf-8 -*-
"""端到端与区分度测试。"""
import os
import sys

import pytest
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from core import align, jd, rules, score, structure

RESUME = os.path.join(ROOT, "tests", "cases", "A_真实强简历.md")

JD_MATCH = """工作职责：
1. 负责游戏内 AI 助手产品的策略产品设计，定义意图路由与知识问答链路
2. 搭建大模型应用的评测体系，定义指标口径，对 badcase 做归因定位
3. 负责 RAG 知识库的知识生产与检索策略设计
任职要求：
1. 本科及以上学历
2. 熟悉 Prompt 工程、Agent 编排、RAG 检索
"""

JD_MISMATCH = """工作职责：
1. 负责 Android 客户端架构设计与核心模块开发
2. 使用 Kotlin 与 Jetpack Compose 重构 UI 层，优化渲染性能
任职要求：
1. 3年以上 Android 开发经验，精通 Kotlin/Java
2. 熟悉 JNI、NDK 与音视频编解码
"""


@pytest.fixture(scope="module")
def kb():
    lex = yaml.safe_load(open(f"{ROOT}/kb/lexicon.yaml", encoding="utf-8"))
    hid = yaml.safe_load(open(f"{ROOT}/kb/hidden_signals.yaml", encoding="utf-8"))
    iss = {i["id"]: i for i in
           yaml.safe_load(open(f"{ROOT}/kb/issues.yaml", encoding="utf-8"))}
    return lex, hid, iss


@pytest.fixture(scope="module")
def resume(kb):
    if not os.path.exists(RESUME):
        pytest.skip("样例简历不在这台机器上")
    return structure.parse(RESUME, kb[0])


def run(resume, kb, jd_text):
    lex, hid, iss = kb
    reqs = jd.parse_jd(jd_text, hid)
    covs = align.align(resume, reqs)
    issues = rules.run_all(resume, iss, lex) + align.fit_issues(resume, reqs, covs, iss)
    return score.score(resume, reqs, covs, issues)


def test_解析出了经历和要点(resume):
    assert len(resume.experiences) >= 2
    assert len(resume.bullets) >= 8
    assert resume.name, "没解析出姓名"


def test_事实台账非空(resume):
    assert resume.facts.numbers and resume.facts.entities


def test_匹配岗位得分显著高于不匹配岗位(resume, kb):
    hit = run(resume, kb, JD_MATCH)["score"]
    miss = run(resume, kb, JD_MISMATCH)["score"]
    assert hit > miss + 20, f"区分度不足：匹配 {hit} vs 不匹配 {miss}"


def test_匹配岗位不应被判为岗位错配(resume, kb):
    s = run(resume, kb, JD_MATCH)
    assert s["score"] >= 42
    assert s["verdict"] != "岗位错配"


def test_每条规则最多列四例(resume, kb):
    from collections import Counter
    issues = rules.run_all(resume, kb[2], kb[0])
    assert all(n <= rules.MAX_PER_RULE for n in Counter(i.id for i in issues).values())


def test_标题行不参与内容规则(resume):
    titles = [b for b in resume.bullets if b.is_title]
    assert all(not b.is_outcome for b in titles)


def test_无JD也能跑(resume, kb):
    s = run(resume, kb, "")
    assert "score" in s
