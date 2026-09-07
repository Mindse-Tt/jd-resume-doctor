# -*- coding: utf-8 -*-
"""JD 结构化拆解（确定性部分）。

四类需求原子：hard_gate 硬性门槛 / core_duty 核心职责 / plus 加分项 /
hidden 隐藏信号。hidden 由 kb/hidden_signals.yaml 显式映射产生，
不允许凭空创造——这是教练经验的沉淀点，必须人工维护。
"""
import re

from .models import RequirementAtom

DUTY_HEAD = re.compile(r"(工作|岗位|职位)?(职责|内容|描述)|你将|Responsibilit", re.I)
REQ_HEAD = re.compile(r"(任职|岗位|职位)?(要求|资格|条件)|我们期待|Requirement|Qualificat", re.I)
PLUS_HEAD = re.compile(r"加分|优先|Nice to have|Bonus", re.I)

HARD_PAT = re.compile(
    r"(本科|硕士|博士|研究生)(及以上)?|"
    r"\d+\s*年(以上)?(相关)?(经验|经历)|"
    r"(必须|需要|要求)(具备|拥有|有)|"
    r"统招|全日制|应届|\d{4}\s*届|英语\s*(六级|CET-?6|流利)")
PLUS_PAT = re.compile(r"优先|加分|更佳|者优先|nice to have", re.I)

from .tokenize import keywords as _keywords


def _split_items(text: str) -> list[tuple[str, str]]:
    """切成 (区块类型, 句子)。区块类型：duty / req / plus / unknown。"""
    zone = "unknown"
    items = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if PLUS_HEAD.search(line) and len(line) < 20:
            zone = "plus"
            continue
        if REQ_HEAD.search(line) and len(line) < 20:
            zone = "req"
            continue
        if DUTY_HEAD.search(line) and len(line) < 20:
            zone = "duty"
            continue
        line = re.sub(r"^\s*[\d]+[.、)）]\s*|^\s*[-•·●*]\s*", "", line)
        # JD 里的元信息和分节抬头不是岗位要求，不该进需求原子
        if re.match(r"^\s*(岗位|职位|职务|部门|团队|所属团队|工作地点|实习类型|"
                    r"招聘对象|毕业时间|基本信息|投递方式|薪资|汇报对象)"
                    r"(名称)?\s*[：:]", line):
            continue
        if re.match(r"^\s*(你会参与的工作|我们希望你|工作职责|岗位职责|任职要求|"
                    r"加分项|职位描述|职位要求|关于我们|团队介绍)\s*[：:]?\s*$", line):
            continue
        for part in re.split(r"[；;]\s*", line):
            part = part.strip()
            if len(part) >= 6:
                items.append((zone, part))
    return items


def parse_jd(text: str, hidden_signals: list[dict], title: str = "") -> list[RequirementAtom]:
    atoms: list[RequirementAtom] = []
    items = _split_items(text)

    duty_seen = 0
    for zone, sent in items:
        if HARD_PAT.search(sent) and zone in ("req", "unknown"):
            typ = "hard_gate"
        elif PLUS_PAT.search(sent) or zone == "plus":
            typ = "plus"
        elif zone == "duty":
            typ = "core_duty"
        elif zone == "req":
            typ = "core_duty"
        else:
            typ = "core_duty"
        atoms.append(RequirementAtom(
            id=f"R-{len(atoms) + 1:02d}", raw=sent, type=typ,
            keywords=_keywords(sent)))
        if typ == "core_duty":
            duty_seen += 1

    # 隐藏信号：只从显式映射表推导
    whole = text
    for sig in hidden_signals:
        hit = next((t for t in sig["trigger"] if t.lower() in whole.lower()), None)
        if not hit:
            continue
        atoms.append(RequirementAtom(
            id=f"R-{len(atoms) + 1:02d}",
            raw=f"（JD 中出现「{hit}」，隐含要求）{sig['implies']}",
            type="hidden", source="inferred", implies=sig["implies"],
            keywords=sig["evidence_hint"]))

    _assign_weights(atoms)
    return atoms


def _assign_weights(atoms: list[RequirementAtom]) -> None:
    """core_duty 占 0.60 权重池并按出现顺序衰减，plus 0.15，hidden 0.15，
    hard_gate 是门控不参与加权。"""
    duties = [a for a in atoms if a.type == "core_duty"]
    plus = [a for a in atoms if a.type == "plus"]
    hidden = [a for a in atoms if a.type == "hidden"]

    if duties:
        decay = [0.92 ** i for i in range(len(duties))]
        s = sum(decay)
        for a, d in zip(duties, decay):
            a.weight = 0.60 * d / s
    for group, pool in ((plus, 0.15), (hidden, 0.15)):
        if group:
            for a in group:
                a.weight = pool / len(group)
    for a in atoms:
        if a.type == "hard_gate":
            a.weight = 0.0
