#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""JD-Resume Doctor 命令行入口。

    python3 jrd.py diagnose --resume 简历.docx [--jd jd.txt] [--title 岗位名] [--out runs/]
    python3 jrd.py web [--port 8899]

确定性层在这里跑完；语义层（JD 深度拆解、蕴含判定、逐句改写）由
skill/SKILL.md 描述的 Claude Code Skill 接手，读 analysis.json 后回写 semantic.json。
"""
import argparse
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import yaml

from core import align as align_mod
from core import jd as jd_mod
from core import report as report_mod
from core import rules as rules_mod
from core import score as score_mod
from core import profile as profile_mod
from core import structure
from core.models import Suggestion
from core.factguard import check_all

ROOT = os.path.dirname(os.path.abspath(__file__))
KB = os.path.join(ROOT, "kb")


def load_kb():
    lexicon = yaml.safe_load(open(os.path.join(KB, "lexicon.yaml"), encoding="utf-8"))
    hidden = yaml.safe_load(open(os.path.join(KB, "hidden_signals.yaml"), encoding="utf-8"))
    issues = {i["id"]: i for i in
              yaml.safe_load(open(os.path.join(KB, "issues.yaml"), encoding="utf-8"))}
    return lexicon, hidden, issues


def diagnose(resume_path, jd_text="", jd_title="", out_dir=None, semantic=None,
             role="ai_pm"):
    lexicon, hidden, kb = load_kb()

    resume = structure.parse(resume_path, lexicon)
    issues = rules_mod.run_all(resume, kb, lexicon)

    # 岗位能力模型体检：没有 JD 也能跑，回答"投这类岗普遍要求什么、你缺哪几项"
    prof_summary, dims = {}, []
    if role:
        try:
            prof_summary, dim_results = profile_mod.evaluate(resume, role)
            issues += profile_mod.profile_issues(dim_results, kb)
            dims = [{"id": d.id, "name": d.name, "weight": d.weight, "level": d.level,
                     "score": d.score, "evidence": d.evidence, "quote": d.quote,
                     "why": d.why, "probe": d.probe, "gap": d.gap, "trap": d.trap,
                     "hits": d.hits} for d in dim_results]
        except FileNotFoundError as e:
            print(f"  [跳过能力模型] {e}")

    reqs, covs = [], []
    if jd_text.strip():
        reqs = jd_mod.parse_jd(jd_text, hidden, jd_title)
        covs = align_mod.align(resume, reqs)
        issues += align_mod.fit_issues(resume, reqs, covs, kb)
        order = {"fatal": 0, "important": 1, "suggestion": 2}
        issues.sort(key=lambda i: (order.get(i.severity, 3), i.id))

    rep = score_mod.build_report(resume, reqs, covs, issues, jd_title)
    rep.profile, rep.dimensions = prof_summary, dims

    # 语义层回写（Skill 产出的 semantic.json）
    if semantic:
        sugg = [Suggestion(**s) for s in semantic.get("suggestions", [])]
        rep.suggestions = check_all(sugg, resume.facts)
        rep.questions = semantic.get("questions", [])
        rep.questions += [s.question for s in rep.suggestions
                          if s.state == "C" and s.question
                          and s.question not in rep.questions]

    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        report_mod.dump_json(rep, os.path.join(out_dir, "analysis.json"))
        # 给 Skill 用的精简输入包
        pack = {
            "resume_name": resume.name, "jd_title": jd_title,
            "facts": {"numbers": resume.facts.numbers[:150],
                      "entities": resume.facts.entities[:150],
                      "periods": resume.facts.periods},
            "bullets": [{"id": b.id, "section": b.section, "label": b.label,
                         "experience": b.experience_id, "raw": b.raw}
                        for b in resume.bullets],
            "experiences": [{"id": e.id, "org": e.org, "role": e.role,
                             "period": e.period_raw} for e in resume.experiences],
            "requirements": [{"id": r.id, "type": r.type, "weight": round(r.weight, 3),
                              "raw": r.raw, "implies": r.implies} for r in reqs],
            "rule_issues": [{"id": i.id, "severity": i.severity, "title": i.title,
                             "bullet_id": i.bullet_id, "detail": i.detail}
                            for i in issues],
            "blockers": rep.blockers,
            "profile": prof_summary,
            "dimensions": [{k: d[k] for k in ("id", "name", "level", "weight",
                                              "evidence", "probe", "gap")} for d in dims],
        }
        with open(os.path.join(out_dir, "pack.json"), "w", encoding="utf-8") as f:
            json.dump(pack, f, ensure_ascii=False, indent=2)
        htmlp = os.path.join(out_dir, "diagnosis.html")
        with open(htmlp, "w", encoding="utf-8") as f:
            f.write(report_mod.render(rep, resume.name or os.path.basename(resume_path),
                                      jd_title))
        return rep, htmlp
    return rep, None


def cmd_diagnose(a):
    jd_text = ""
    if a.jd:
        jd_text = open(a.jd, encoding="utf-8").read()
    semantic = json.load(open(a.semantic, encoding="utf-8")) if a.semantic else None
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out = a.out or os.path.join(ROOT, "runs",
                                f"{stamp}_{os.path.splitext(os.path.basename(a.resume))[0]}")
    rep, htmlp = diagnose(a.resume, jd_text, a.title, out, semantic, a.role)

    if rep.profile:
        c = rep.profile["counts"]
        print(f"\n  【{rep.profile['role_name']} 能力体检】 {rep.profile['score']:.0f} / 100"
              f"    {rep.profile['label']}")
        print(f"  强证据 {c['L3']} 项 · 只做没说清 {c['L2']} 项 · "
              f"沾边 {c['L1']} 项 · 完全没有 {c['L0']} 项")
        weak = [d for d in rep.dimensions if d["level"] in ("L0", "L1")]
        for d in sorted(weak, key=lambda x: -x["weight"])[:3]:
            print(f"    ✗ {d['name']}（{d['level']}）")
    print(f"\n  匹配度 {rep.score:.0f} / 100    {rep.verdict}")
    print(f"  {rep.metrics.get('建议','')}")
    if rep.hard_gate_failures:
        print("\n  硬性门槛未体现：")
        for g in rep.hard_gate_failures:
            print(f"    ✗ {g}")
    sev = {"fatal": 0, "important": 0, "suggestion": 0}
    for i in rep.issues:
        sev[i.severity] = sev.get(i.severity, 0) + 1
    print(f"\n  问题：致命 {sev['fatal']} · 重要 {sev['important']} · 建议 {sev['suggestion']}")
    if rep.blockers:
        print("\n  最卡的几件事：")
        for b in rep.blockers:
            tag = {"FIXABLE_NOW": "做过但没写", "REWRITE_ONLY": "写了但看不出来",
                   "NEED_EXPERIENCE": "没做过"}.get(b["fixability"], "?")
            print(f"    [{tag}] {b['req'][:52]}")
    print(f"\n  报告：{htmlp}\n  语义层输入包：{os.path.join(out,'pack.json')}\n")


def cmd_web(a):
    from web.server import serve
    serve(a.port)


def main():
    p = argparse.ArgumentParser(prog="jrd", description="按 JD 诊断简历")
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("diagnose", help="诊断一份简历")
    d.add_argument("--resume", required=True)
    d.add_argument("--jd", help="JD 文本文件")
    d.add_argument("--title", default="", help="岗位名")
    d.add_argument("--out", help="输出目录")
    d.add_argument("--semantic", help="Skill 产出的 semantic.json")
    d.add_argument("--role", default="ai_pm",
                   help="岗位能力模型（kb/role_profiles 下的文件名），传空字符串跳过")
    d.set_defaults(func=cmd_diagnose)

    w = sub.add_parser("web", help="启动本地网页版")
    w.add_argument("--port", type=int, default=8899)
    w.set_defaults(func=cmd_web)

    a = p.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()
