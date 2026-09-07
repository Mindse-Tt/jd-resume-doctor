# -*- coding: utf-8 -*-
"""评分与卡点定位。

分数必须能展开成"哪条要求贡献了多少分"，否则就是黑盒。
最有价值的输出不是分数，是把问题分成三类：
没做过 / 做过但没写 / 写了但看不出来。
"""
from .models import Coverage, Issue, RequirementAtom, Report, Resume

PENALTY = {"fatal": 9, "important": 4, "suggestion": 1.5}

# 阈值按真实样本标定：结构上的实际满分约 85，不是 100
BANDS = [
    (72, "可以投", "匹配度够了，重点打磨面试故事和追问准备。"),
    (58, "改写后可投", "有 2-3 个明显可修补的表达问题，改完再投。"),
    (42, "需要重构", "相关经历有，但呈现方式或排布要动大手术。"),
    (0,  "岗位错配", "建议换方向，或先补一段相关经历再投。"),
]


def features(resume: Resume) -> dict:
    outs = [b for b in resume.bullets if b.is_outcome]
    lv = [b.verb_level for b in resume.bullets if b.verb_level]
    lens = sorted(b.char_len for b in resume.bullets) or [0]
    return {
        "bullets": len(resume.bullets),
        "experiences": len(resume.experiences),
        "量化密度": round(sum(1 for b in outs if b.has_number) / len(outs), 3) if outs else 0.0,
        "带基线的指标数": sum(1 for b in resume.bullets
                             for m in b.metrics if m.has_baseline),
        "强动词占比": round(sum(1 for x in lv if x == 3) / len(lv), 3) if lv else 0.0,
        "弱动词占比": round(sum(1 for x in lv if x == 1) / len(lv), 3) if lv else 0.0,
        "要点长度中位数": lens[len(lens) // 2],
        "超长要点占比": round(sum(1 for x in lens if x > 90) / len(lens), 3) if lens else 0.0,
        "正文字数": len(resume.raw_text.replace("\n", "")),
    }


def score(resume: Resume, reqs: list[RequirementAtom], covs: list[Coverage],
          issues: list[Issue]) -> dict:
    by_id = {c.req_id: c for c in covs}

    def pool(kind):
        items = [(r, by_id.get(r.id)) for r in reqs if r.type == kind]
        items = [(r, c) for r, c in items if c]
        w = sum(r.weight for r, _ in items)
        if not w:
            return 0.0, 0.0
        return sum(r.weight * c.strength for r, c in items) / w, w

    core, _ = pool("core_duty")
    plus, _ = pool("plus")
    hidden, _ = pool("hidden")

    # 同一条规则命中多次做递减，否则一条规则就能把呈现质量打到地板
    from collections import Counter
    counts = Counter(i.id for i in issues if not i.id.startswith("FIT-"))
    sev_of = {i.id: i.severity for i in issues}
    penalty = sum(PENALTY.get(sev_of[rid], 1) * (1 + 0.4 * (n - 1))
                  for rid, n in counts.items())
    budget = 18 + 3.2 * max(len(resume.bullets), 1)     # 按要点数给扣分预算
    present = max(0.10, 1.0 - penalty / budget)

    gates = [r for r in reqs if r.type == "hard_gate"
             and by_id.get(r.id) and by_id[r.id].level in ("L0", "L1")]

    total = 0.60 * core + 0.15 * plus + 0.15 * hidden + 0.10 * present
    total = round(total * 100, 1)

    if gates:
        verdict = "简历层面大概率过不了（硬性门槛未体现）"
    else:
        verdict = next(v for lo, v, _ in BANDS if total >= lo)
    advice = next(a for lo, _, a in BANDS if total >= lo)

    return {
        "score": total, "verdict": verdict, "advice": advice,
        "sub_scores": {"核心职责匹配": round(core * 100, 1),
                       "加分项": round(plus * 100, 1),
                       "隐藏信号": round(hidden * 100, 1),
                       "呈现质量": round(present * 100, 1)},
        "hard_gate_failures": [r.raw[:80] for r in gates],
    }


def blockers(reqs: list[RequirementAtom], covs: list[Coverage], top=5) -> list[dict]:
    """blocker_score = 权重 × (1 - 证据强度)。这就是"最卡的几件事"。"""
    by_id = {r.id: r for r in reqs}
    rows = []
    for c in covs:
        r = by_id.get(c.req_id)
        if not r or r.weight <= 0:
            continue
        rows.append({
            "req": r.raw[:90], "type": r.type, "weight": round(r.weight, 3),
            "level": c.level, "strength": c.strength,
            "blocker_score": round(r.weight * (1 - c.strength), 4),
            "fixability": c.fixability, "why": c.gap_reason,
            "cited": c.cited,
        })
    rows.sort(key=lambda x: -x["blocker_score"])
    return rows[:top]


def build_report(resume, reqs, covs, issues, jd_title="") -> Report:
    s = score(resume, reqs, covs, issues)
    return Report(
        resume_path=resume.path, jd_title=jd_title,
        verdict=s["verdict"], score=s["score"], sub_scores=s["sub_scores"],
        metrics=features(resume) | {"建议": s["advice"],
                                    "可安全改写": resume.editable,
                                    "降级原因": resume.editable_reason},
        hard_gate_failures=s["hard_gate_failures"],
        blockers=blockers(reqs, covs), issues=issues,
        coverage=covs, requirements=reqs,
    )
