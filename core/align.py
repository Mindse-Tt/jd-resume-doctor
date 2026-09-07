# -*- coding: utf-8 -*-
"""需求原子 × 证据原子的覆盖对齐。

不用余弦相似度——它只能告诉你"像不像"，不能告诉你"哪条要求没被满足"，
更不能作为改简历的依据。这里走：BM25 召回 → 覆盖等级判定 → 证据强度加权。
LLM 版的蕴含判定由 Skill 层覆盖同样的 Coverage 结构。
"""
import math
import re
from collections import Counter

from .models import Bullet, Coverage, Issue, RequirementAtom, Resume
from .tokenize import cut

BASE = {"L3": 1.0, "L2": 0.70, "L1": 0.35, "L0": 0.0}
ROLE_FACTOR = {"lead": 1.0, "co_lead": 0.85, "participant": 0.6,
               "support": 0.4, "unknown": 0.7}


def _tok(s: str) -> list[str]:
    return cut(s)


class BM25:
    def __init__(self, docs: list[list[str]], k1=1.5, b=0.75):
        self.docs, self.k1, self.b = docs, k1, b
        self.N = max(len(docs), 1)
        self.avgdl = sum(len(d) for d in docs) / self.N if docs else 1.0
        self.df = Counter()
        for d in docs:
            for t in set(d):
                self.df[t] += 1

    def score(self, q: list[str], i: int) -> float:
        d = self.docs[i]
        if not d:
            return 0.0
        tf = Counter(d)
        s = 0.0
        for t in q:
            if t not in tf:
                continue
            idf = math.log(1 + (self.N - self.df[t] + 0.5) / (self.df[t] + 0.5))
            s += idf * tf[t] * (self.k1 + 1) / (
                tf[t] + self.k1 * (1 - self.b + self.b * len(d) / self.avgdl))
        return s


def _hit_ratio(keywords: list[str], text: str) -> float:
    """关键词命中率。关键词可能是正则（如 "评测|评估"），先按正则试，失败再按字面。"""
    if not keywords:
        return 0.0
    hits = 0
    for kw in keywords:
        try:
            if re.search(kw, text, re.I):
                hits += 1
                continue
        except re.error:
            pass
        if kw.lower() in text.lower():
            hits += 1
    return hits / len(keywords)


def _role_of(b: Bullet, resume: Resume) -> str:
    text = b.raw
    exp = next((e for e in resume.experiences if e.id == b.experience_id), None)
    if exp:
        text = exp.org + " " + text
    if re.search(r"独立负责|主导|牵头|从\s*0|0\s*[→\-]\s*1|自建|独立设计", text):
        return "lead"
    if re.search(r"共同|协同|合作|与.{1,8}(团队|同学|部门)", text):
        return "co_lead"
    if re.search(r"参与|参加", text):
        return "participant"
    if re.search(r"协助|配合|支持", text):
        return "support"
    return "unknown"


def _quant_factor(b: Bullet) -> float:
    if any(m.has_baseline for m in b.metrics):
        return 1.0
    if b.has_number:
        return 0.88
    return 0.76


def _recency_factor(b: Bullet, resume: Resume) -> float:
    exp = next((e for e in resume.experiences if e.id == b.experience_id), None)
    if not exp:
        return 0.92
    ys = re.findall(r"20\d{2}", exp.period_raw)
    if not ys:
        return 0.95
    latest = max(int(y) for y in ys)
    if re.search(r"至今|now|present", exp.period_raw, re.I):
        return 1.0
    return max(0.7, 1.0 - 0.06 * max(0, 2026 - latest))


def align(resume: Resume, reqs: list[RequirementAtom],
          topk: int = 5) -> list[Coverage]:
    docs = [_tok(b.raw + " " + b.label) for b in resume.bullets]
    bm = BM25(docs)
    covs: list[Coverage] = []

    for req in reqs:
        q = _tok(" ".join(req.keywords) + " " + req.raw)
        scored = sorted(((bm.score(q, i), i) for i in range(len(docs))),
                        reverse=True)[:topk]
        scored = [(s, i) for s, i in scored if s > 0]
        ratio = _hit_ratio(req.keywords, resume.raw_text)

        # 门槛项只看事实在不在，不走检索召回（学历这类词不会出现在要点里）
        if req.type == "hard_gate":
            lvl = "L3" if ratio >= 0.4 else "L2" if ratio >= 0.2 else "L0"
            covs.append(Coverage(
                req.id, lvl, [], {"L3": 1.0, "L2": 0.7, "L0": 0.0}[lvl],
                "门槛已在简历中体现" if lvl != "L0" else "简历中未体现该门槛",
                "REWRITE_ONLY" if lvl != "L0" else "NEED_EXPERIENCE"))
            continue

        if not scored:
            covs.append(Coverage(req.id, "L0", [], 0.0,
                                 "简历中找不到任何相关内容",
                                 "NEED_EXPERIENCE"))
            continue

        best_i = scored[0][1]
        best = resume.bullets[best_i]
        role = _role_of(best, resume)

        # 字面命中 + 检索得分的组合信号，单独用任何一个都会误判
        signal = 0.65 * ratio + 0.35 * min(1.0, scored[0][0] / 25.0)

        if signal >= 0.60 and best.has_number:
            level = "L3"
        elif signal >= 0.72 and role == "lead":
            level = "L3"            # 主导且高度相关，允许没数字也算直接证明
        elif signal >= 0.38:
            level = "L2"
        elif signal >= 0.20:
            level = "L1"
        else:
            level = "L0"

        cited = [resume.bullets[i].id for _, i in scored[:3]]
        if level == "L0":
            cited = []                      # 引用为空一律降为 L0，防幻觉闸门

        # 四个因子连乘会把分数压死；用加权混合，让因子只做调节而非否决
        adj = (ROLE_FACTOR[role] * _quant_factor(best)
               * _recency_factor(best, resume))
        strength = BASE[level] * (0.55 + 0.45 * adj)

        if level == "L0":
            fix, reason = "NEED_EXPERIENCE", "简历中无对应证据，需要补经历或换岗位"
        elif level == "L1":
            fix, reason = "FIXABLE_NOW", "只有可迁移的相关经历，需要补写领域相关的具体做法"
        elif not best.has_number:
            fix, reason = "REWRITE_ONLY", "做过但没写出结果，补口径和数字即可"
        else:
            fix, reason = "REWRITE_ONLY", "已有证据，可通过换词/前置强化匹配度"

        covs.append(Coverage(req.id, level, cited, round(strength, 3), reason, fix))
    return covs


def fit_issues(resume: Resume, reqs: list[RequirementAtom],
               covs: list[Coverage], kb: dict) -> list[Issue]:
    """把对齐结果翻译成 FIT-* 问题条目。"""
    by_id = {c.req_id: c for c in covs}
    out: list[Issue] = []

    def mk(rid, detail, quote):
        k = kb[rid]
        return Issue(id=rid, category=k["category"], severity=k["severity"],
                     title=k["title"], detail=detail, quote=quote,
                     interviewer_view=k.get("interviewer_view", ""),
                     fix_hint=k.get("fix_hint", ""))

    for req in reqs:
        c = by_id.get(req.id)
        if not c:
            continue
        if req.type == "hard_gate" and c.level in ("L0", "L1"):
            out.append(mk("FIT-01", f"门槛项未在简历中体现：{c.gap_reason}", req.raw[:70]))
        elif req.type == "core_duty" and c.level == "L0":
            out.append(mk("FIT-02", f"核心职责无对应证据（权重 {req.weight:.2f}）", req.raw[:70]))
        elif req.type == "hidden" and c.level in ("L0", "L1"):
            out.append(mk("FIT-06", f"隐含要求：{req.implies}", req.raw[:70]))

    # 关键词字面缺失（ATS 风险）
    missing = []
    for req in reqs:
        if req.type not in ("core_duty", "hard_gate"):
            continue
        for kw in req.keywords[:6]:
            if len(kw) < 2 or kw in missing:
                continue
            if _hit_ratio([kw], resume.raw_text) == 0.0:
                missing.append(kw)
    if len(missing) >= 5:
        out.append(mk("FIT-03",
                      f"{len(missing)} 个 JD 关键词在简历中一次都没出现",
                      "、".join(missing[:12])))
    return out
