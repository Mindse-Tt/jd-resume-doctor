# -*- coding: utf-8 -*-
"""知识库自检。KB 是纯数据资产，教练会直接手改，
所以「能不能解析」和「字段齐不齐」必须有回归测试兜住。"""
import glob
import os

import pytest
import yaml

KB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "kb")


@pytest.mark.parametrize("path", sorted(glob.glob(f"{KB}/**/*.yaml", recursive=True)))
def test_每个yaml都能解析(path):
    assert yaml.safe_load(open(path, encoding="utf-8")) is not None


def test_问题规则字段齐全():
    for item in yaml.safe_load(open(f"{KB}/issues.yaml", encoding="utf-8")):
        for f in ("id", "category", "severity", "title", "interviewer_view", "fix_hint"):
            assert item.get(f), f"{item.get('id')} 缺字段 {f}"
        assert item["severity"] in ("fatal", "important", "suggestion")


@pytest.mark.parametrize("path", sorted(glob.glob(f"{KB}/role_profiles/*.yaml")))
def test_岗位模型权重归一(path):
    prof = yaml.safe_load(open(path, encoding="utf-8"))
    total = sum(d["weight"] for d in prof["dimensions"])
    assert abs(total - 1.0) < 1e-6, f"{path} 权重和为 {total}，应为 1"


@pytest.mark.parametrize("path", sorted(glob.glob(f"{KB}/role_profiles/*.yaml")))
def test_每个维度都有追问和信号(path):
    prof = yaml.safe_load(open(path, encoding="utf-8"))
    for d in prof["dimensions"]:
        assert d.get("probe"), f"{d['id']} 没有面试官追问——维度成立的唯一检验"
        assert d.get("signals"), f"{d['id']} 没有 signals，检索不到证据"
        assert set(d.get("levels", {})) == {"L1", "L2", "L3"}, f"{d['id']} 等级定义不全"


def test_分档从高到低有序():
    for path in glob.glob(f"{KB}/role_profiles/*.yaml"):
        bands = yaml.safe_load(open(path, encoding="utf-8"))["bands"]
        mins = [b["min_score"] for b in bands]
        assert mins == sorted(mins, reverse=True), f"{path} 分档没有从高到低排"
