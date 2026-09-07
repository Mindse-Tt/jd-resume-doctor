# -*- coding: utf-8 -*-
"""对着岗位能力模型体检。

和 align.py 的区别：align 是「这份简历 vs 这个 JD」，profile 是
「这份简历 vs 这个岗位普遍要求什么」——所以没有 JD 也能诊断。

判定逻辑刻意做成正向的：先看每个维度有没有强证据，缺的才是问题。
这比拍脑袋列负面清单可扩展——换岗位只要换一个 profile YAML。
"""
import os
import re
from dataclasses import dataclass, field

import yaml

from .models import Issue, Resume

KB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "kb", "role_profiles")

LEVEL_SCORE = {"L3": 1.0, "L2": 0.55, "L1": 0.22, "L0": 0.0}
SEVERITY_BY_WEIGHT = [(0.11, "important"), (0.0, "suggestion")]


@dataclass
class DimResult:
    id: str
    name: str
    weight: float
    level: str = "L0"
    score: float = 0.0
    hits: dict = field(default_factory=dict)      # signal 组 -> 命中次数
    evidence: list = field(default_factory=list)  # bullet id
    quote: str = ""
    why: str = ""
    probe: str = ""
    gap: str = ""
    trap: str = ""


def available() -> list[str]:
    if not os.path.isdir(KB_DIR):
        return []
    return sorted(f[:-5] for f in os.listdir(KB_DIR) if f.endswith(".yaml"))


def load(role: str = "ai_pm") -> dict:
    path = os.path.join(KB_DIR, f"{role}.yaml")
    if not os.path.isfile(path):
        raise FileNotFoundError(f"没有这个岗位模型：{role}（可用：{', '.join(available())}）")
    return yaml.safe_load(open(path, encoding="utf-8"))


# 「说了为什么」的语言标记——这是 L2 升 L3 的关键判据
REASONING = re.compile(
    r"因为|由于|之所以|原因是|考虑到|权衡|取舍|trade[- ]?off|"
    r"而非|而不是|不是.{1,10}而是|否则|反之|与.{1,12}相反|"
    r"——|所以.{0,4}(选|用|采用|上提|下沉)|判断.{0,6}(适合|不适合)|"
    r"瓶颈(不)?在|关键(不)?在|本质(上)?是")

# 口径 / 规模标记——有这些说明数字不是拍的
RIGOR = re.compile(r"口径|评测集|样本|标注|基线|条(数据|标注|QA|评测)?|"
                   r"Top\s*\d|一致性|统计|双人|抽检|环比|同比")


# 行话表：只用来度量"说了多少术语"，不用来判能力
JARGON = re.compile(
    r"RAG|Agent|Planner|tool|prompt|embedding|badcase|北极星|向量检索|精确检索|"
    r"知识库|评测(体系|平台|集)|意图(识别|路由)|归因|拒答|OOC|Workflow|Skill|token|"
    r"多轮|召回|重排|rerank|微调|上下文|大模型|LLM|冷启动|漏斗|指标塔",
    re.I)

# 具体性：有数字、有引号里的实指、有举例
CONCRETE = re.compile(r"[0-9]|[""「」]|例如|比如|其中|具体")


def substance(resume) -> dict:
    """度量"实质"，与行话量分开算。

    术语堆砌型简历的特征是行话密度高但具体性为零；
    真做过的人行话和具体性同时高。这两个维度必须分开测，
    否则堆砌者和真人分不开——这是 v0.1 实测出来的最大漏洞。
    """
    bs = [b for b in resume.bullets if not b.is_title and len(b.raw) > 20]
    if not bs:
        return {"bullets": 0, "行话密度": 0.0, "具体性": 0.0, "因果比例": 0.0,
                "堆砌指数": 0.0, "疑似术语堆砌": False, "行话过少": False}
    chars = sum(len(b.raw) for b in bs)
    jd = sum(len(JARGON.findall(b.raw)) for b in bs) / chars * 1000
    conc = sum(1 for b in bs if CONCRETE.search(b.raw)) / len(bs)
    caus = sum(1 for b in bs if REASONING.search(b.raw)) / len(bs)
    stuffing = jd / (conc * 100 + 8)
    return {
        "bullets": len(bs),
        "行话密度": round(jd, 1), "具体性": round(conc, 2),
        "因果比例": round(caus, 2), "堆砌指数": round(stuffing, 2),
        "疑似术语堆砌": stuffing > 1.5 and caus < 0.15,
        # 正文不少但几乎不用行话 → 规则层大概率漏判，必须上语义层
        "行话过少": jd < 8 and chars > 300,
    }


def _excerpt(text: str, patterns: list[str], width: int = 120) -> str:
    """以命中处为中心取一段引文。按前 N 字硬截会把命中的词截掉，
    读者就看不出这句话凭什么算证据。"""
    pos = -1
    for p in patterns:
        try:
            m = re.search(p, text, re.I)
        except re.error:
            m = None
        if m:
            pos = m.start() if pos < 0 else min(pos, m.start())
    if pos < 0 or len(text) <= width:
        return text[:width]
    start = max(0, pos - width // 3)
    end = min(len(text), start + width)
    return ("…" if start > 0 else "") + text[start:end] + ("…" if end < len(text) else "")


def _match_count(patterns: list[str], text: str) -> int:
    n = 0
    for p in patterns:
        try:
            if re.search(p, text, re.I):
                n += 1
        except re.error:
            if p.lower() in text.lower():
                n += 1
    return n


def evaluate(resume: Resume, role: str = "ai_pm") -> tuple[dict, list[DimResult]]:
    prof = load(role)
    text = resume.raw_text
    results: list[DimResult] = []

    for dim in prof["dimensions"]:
        sigs = dim.get("signals", [])

        # 逐句判定。信号、因果论述、口径必须出现在同一句里才算数——
        # 否则简历里任何一处的"因为"都会让每个维度都显得有论述。
        # signals[0] 是这个维度的定义性信号，必须命中才算证据；
        # 其余组只用来衡量深度。否则「归因」这种通用词会把无关句子拉进来。
        core_sig, depth_sigs = sigs[:1], sigs[1:]

        cands = []      # (组数, 有因果, 有口径, bullet)
        for b in resume.bullets:
            if b.is_title or _match_count(core_sig, b.raw) == 0:
                continue
            g = 1 + _match_count(depth_sigs, b.raw)
            cands.append((g, bool(REASONING.search(b.raw)),
                          bool(RIGOR.search(b.raw)), b))

        ev = [c[3].id for c in cands]
        depth = len(cands)
        best = max(cands, key=lambda c: (c[0], c[1], c[2])) if cands else None
        best_g = best[0] if best else 0
        groups_hit = best_g
        has_reasoning = any(c[0] >= 2 and c[1] for c in cands)
        has_rigor = any(c[0] >= 2 and c[2] for c in cands)
        strong = next((c[3].raw for c in sorted(
            cands, key=lambda c: (-(c[0]), not (c[1] or c[2])))
            if c[0] >= 2 and (c[1] or c[2])), None)
        quotes = [_excerpt(best[3].raw, core_sig)] if best else []

        # 正向判级：有证据 → 证据够密 → 同一句里还讲了为什么
        if depth == 0:
            level = "L0"
        elif strong and depth >= 2:
            level = "L3"
        elif best_g >= 2 or depth >= 2:
            level = "L2"
        else:
            level = "L1"

        gap = {
            "L3": "",
            "L2": "有做过的证据，但没写出「为什么这么设计」——"
                  "而这正是面试官唯一会追问的地方",
            "L1": "只沾到边，看不出体系。要么补细节，要么这项就别写",
            "L0": "简历里完全没有这一项的证据",
        }[level]

        results.append(DimResult(
            id=dim["id"], name=dim["name"], weight=float(dim["weight"]),
            level=level, score=LEVEL_SCORE[level],
            hits={"最强句信号组": groups_hit, "承载句数": depth,
                  "同句因果论述": has_reasoning, "同句口径/规模": has_rigor},
            evidence=ev[:4],
            quote=(_excerpt(strong, core_sig) if strong
                   else (quotes[0] if quotes else "")),
            why=dim.get("why", "").strip(), probe=dim.get("probe", "").strip(),
            gap=gap, trap=dim.get("trap", "").strip(),
        ))

    sub = substance(resume)

    # 术语堆砌：行话铺满但没有一个具体对象、没有一句因果。
    # 这种简历每个维度的定义性信号都命中，不封顶的话会和真做过的人同分。
    if sub["疑似术语堆砌"]:
        for d in results:
            if d.level in ("L3", "L2"):
                d.level, d.score = "L1", LEVEL_SCORE["L1"]
                d.gap = ("命中了这个维度的术语，但通篇没有具体对象、没有数字、"
                         "也没有一句「为什么这么做」——按术语堆砌处理")

    total = sum(d.weight * d.score for d in results)
    band = next(b for b in prof["bands"] if total >= b["min_score"])

    # 规则层靠行话正则召回，抓不到用大白话讲清楚的人。
    # 这种情况下分数不作数，必须交给语义层重判。
    need_semantic = sub["行话过少"] and sum(
        1 for d in results if d.level == "L0") >= len(results) * 0.6

    summary = {
        "role": prof["role"], "role_name": prof["name"],
        "version": prof.get("version", ""),
        "score": round(total * 100, 1),
        "label": band["label"], "advice": band["advice"],
        "counts": {lv: sum(1 for d in results if d.level == lv)
                   for lv in ("L3", "L2", "L1", "L0")},
        "substance": sub,
        "疑似术语堆砌": sub["疑似术语堆砌"],
        "需要语义层重判": need_semantic,
        "置信度": "低" if (need_semantic or sub["疑似术语堆砌"]) else "中",
    }
    if sub["疑似术语堆砌"]:
        summary["label"] = "疑似术语堆砌，判定已封顶"
        summary["advice"] = (
            "术语都写到了，但没有一处具体对象或因果论述。面试官问第一个"
            "「具体怎么做的」就会穿。要么补细节，要么删掉这些词。")
    if need_semantic:
        summary["label"] = "规则层判不了，待语义层重判"
        summary["advice"] = (
            "这份简历几乎不用行业术语，规则层召回不到证据，"
            "上面的分数不作数——必须由语义层逐条重判。")
    return summary, results


def profile_issues(results: list[DimResult], kb: dict) -> list[Issue]:
    """把能力模型上的缺口翻译成问题条目——负面清单从正向模型里推导出来，
    而不是反过来。"""
    out: list[Issue] = []
    for d in sorted(results, key=lambda x: -x.weight):
        if d.level == "L3":
            continue
        sev = next(s for w, s in SEVERITY_BY_WEIGHT if d.weight >= w)
        if d.level == "L0" and d.weight >= 0.11:
            sev = "important"
        out.append(Issue(
            id=f"AIPM-{d.id}", category="AI 产品能力",
            severity=sev, title=f"{d.name}：{d.level}",
            detail=d.gap,
            quote=d.quote or "（简历里找不到承载这一项的句子）",
            interviewer_view=f"面试官会问：{d.probe}",
            fix_hint=(f"常见陷阱：{d.trap}" if d.trap else ""),
        ))
    return out[:8]
