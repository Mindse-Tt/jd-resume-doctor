# -*- coding: utf-8 -*-
"""单文件 HTML 报告。内联全部样式，无外链，可直接微信/飞书转发。"""
import html
import json
from datetime import date

from .models import Report

SEV = {"fatal": ("致命", "#B4232B", "#FCEDED"),
       "important": ("重要", "#B26A00", "#FFF6E6"),
       "suggestion": ("建议", "#2C6E9B", "#EDF5FA")}

LEVEL = {"L3": ("强证据", "#1F7A4D", "#E9F6EF"),
         "L2": ("做了没说清", "#B26A00", "#FFF6E6"),
         "L1": ("只沾到边", "#9A5B08", "#FBF2E4"),
         "L0": ("完全没有", "#B4232B", "#FCEDED")}

FIX = {"FIXABLE_NOW": ("做过但没写", "#1F7A4D", "#E9F6EF"),
       "REWRITE_ONLY": ("写了但看不出来", "#B26A00", "#FFF6E6"),
       "NEED_EXPERIENCE": ("没做过", "#B4232B", "#FCEDED"),
       "UNKNOWN": ("待判定", "#5A6672", "#EEF1F4")}

CSS = """
:root{--ink:#151A20;--sub:#5A6672;--line:#E3E7EC;--bg:#F5F7F9;--card:#fff;--acc:#005FA2}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font:15px/1.65 -apple-system,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif}
.wrap{max-width:940px;margin:0 auto;padding:28px 20px 64px}
h1{font-size:25px;margin:0 0 4px;letter-spacing:-.2px}
h2{font-size:17px;margin:34px 0 12px;padding-bottom:7px;border-bottom:2px solid var(--acc);
   color:var(--acc);letter-spacing:.3px}
.meta{color:var(--sub);font-size:13px;margin-bottom:22px}
.card{background:var(--card);border:1px solid var(--line);border-radius:11px;
      padding:16px 18px;margin-bottom:12px}
.hero{display:flex;gap:22px;align-items:center;flex-wrap:wrap}
.dial{width:118px;height:118px;border-radius:50%;flex:0 0 auto;display:grid;place-items:center;
      color:#fff;font-weight:700;line-height:1.1;text-align:center}
.dial b{font-size:31px;display:block}
.dial span{font-size:11px;opacity:.9}
.verdict{font-size:20px;font-weight:700;margin-bottom:4px}
.advice{color:var(--sub)}
.subs{display:grid;grid-template-columns:repeat(auto-fit,minmax(148px,1fr));gap:10px;margin-top:14px}
.sub{background:var(--card);border:1px solid var(--line);border-radius:9px;padding:11px 13px}
.sub i{font-style:normal;color:var(--sub);font-size:12px;display:block}
.sub b{font-size:21px}
.bar{height:5px;border-radius:3px;background:#EDF0F3;margin-top:7px;overflow:hidden}
.bar i{display:block;height:100%;background:var(--acc)}
.tag{display:inline-block;padding:1px 8px;border-radius:5px;font-size:11.5px;
     font-weight:600;margin-right:7px;vertical-align:2px;white-space:nowrap}
.issue{border-left:3px solid var(--line);padding-left:13px;margin:13px 0}
.issue .t{font-weight:650}
.quote{background:#F7F9FB;border:1px dashed var(--line);border-radius:7px;padding:8px 11px;
       margin:7px 0;color:#33404D;font-size:13.5px;white-space:pre-wrap}
.hint{color:#1F7A4D;font-size:13.5px;margin-top:5px}
.view{color:var(--sub);font-size:13.5px;margin-top:5px}
table{width:100%;border-collapse:collapse;font-size:13.5px}
th,td{text-align:left;padding:9px 10px;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--sub);font-weight:600;font-size:12.5px;background:#FAFBFC}
.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12.5px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:9px}
.kv{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:9px 12px}
.kv i{font-style:normal;color:var(--sub);font-size:12px;display:block}
.kv b{font-size:16px}
.note{background:#FFF9E8;border:1px solid #F0DFAE;border-radius:9px;padding:13px 15px;
      font-size:13.5px;color:#6B5312;margin-top:26px}
.empty{color:var(--sub);padding:8px 0}
.dim{display:grid;grid-template-columns:15px 1fr auto;gap:0 12px;align-items:start;
     padding:13px 0;border-bottom:1px solid var(--line)}
.dim:last-child{border-bottom:0}
.dim .rail{grid-row:1/span 3;width:4px;border-radius:2px;height:100%;min-height:34px}
.dim .nm{font-weight:650;font-size:14.5px}
.dim .lv{text-align:right;white-space:nowrap}
.dim .w{color:var(--sub);font-size:11.5px;font-family:ui-monospace,Menlo,monospace}
.dim .gap{grid-column:2/4;color:var(--sub);font-size:13px;margin-top:3px}
.dim .probe{grid-column:2/4;font-size:13px;margin-top:4px;color:#33404D}
.dim .ev{grid-column:2/4;background:#F7F9FB;border:1px dashed var(--line);border-radius:6px;
         padding:6px 9px;margin-top:6px;font-size:12.5px;color:#33404D}
.legend{display:flex;flex-wrap:wrap;gap:6px 14px;font-size:12.5px;color:var(--sub);
        margin-top:12px;padding-top:11px;border-top:1px solid var(--line)}
@media print{body{background:#fff}.card,.sub,.kv{break-inside:avoid}}
"""


def _tag(text, fg, bg):
    return f'<span class="tag" style="color:{fg};background:{bg}">{text}</span>'


def _dial_color(score, gate):
    if gate:
        return "#B4232B"
    return "#1F7A4D" if score >= 80 else "#B26A00" if score >= 65 else "#B4232B"


def render(rep: Report, resume_name="", jd_title="") -> str:
    e = html.escape
    gate = bool(rep.hard_gate_failures)
    o = [f'<meta charset="utf-8"><meta name="viewport" content="width=device-width,'
         f'initial-scale=1"><title>简历诊断 · {e(resume_name or "报告")}</title>'
         f"<style>{CSS}</style><div class='wrap'>"]

    o.append(f"<h1>简历诊断报告</h1><div class='meta'>"
             f"{e(resume_name or rep.resume_path)}　·　目标岗位：{e(jd_title or '未指定')}"
             f"　·　{date.today()}</div>")

    # 岗位能力体检——没有 JD 也能看，所以放在最前面
    if rep.profile:
        p = rep.profile
        c = p["counts"]
        pc = ("#1F7A4D" if p["score"] >= 72 else
              "#B26A00" if p["score"] >= 55 else "#B4232B")
        o.append(f"<h2>{e(p['role_name'])} · 能力体检</h2>")
        o.append("<div class='card hero'>")
        o.append(f"<div class='dial' style='background:{pc}'>"
                 f"<div><b>{p['score']:.0f}</b><span>能力分</span></div></div>")
        o.append(f"<div style='flex:1;min-width:250px'><div class='verdict'>{e(p['label'])}</div>"
                 f"<div class='advice'>{e(p['advice'])}</div>"
                 f"<div class='advice' style='margin-top:7px;font-size:13px'>"
                 f"强证据 {c['L3']} 项 · 做了没说清 {c['L2']} 项 · "
                 f"只沾到边 {c['L1']} 项 · 完全没有 {c['L0']} 项</div></div></div>")

        o.append("<div class='card'>")
        for d in sorted(rep.dimensions, key=lambda x: -x["weight"]):
            label, fg, bg = LEVEL.get(d["level"], LEVEL["L0"])
            o.append(f"<div class='dim'><div class='rail' style='background:{fg}'></div>"
                     f"<div class='nm'>{e(d['name'])}"
                     f"<span class='w'>　权重 {d['weight']:.2f}</span></div>"
                     f"<div class='lv'>{_tag(d['level'] + ' ' + label, fg, bg)}</div>")
            if d.get("gap"):
                o.append(f"<div class='gap'>{e(d['gap'])}</div>")
            if d["level"] != "L3" and d.get("probe"):
                o.append(f"<div class='probe'>面试官会问：{e(d['probe'])}</div>")
            if d.get("quote") and d["level"] in ("L3", "L2"):
                o.append(f"<div class='ev'>简历里的证据：{e(d['quote'])}</div>")
            o.append("</div>")
        o.append("<div class='legend'>"
                 "<span><b>L3</b> 说清了为什么这么设计</span>"
                 "<span><b>L2</b> 有做过的证据，没写为什么</span>"
                 "<span><b>L1</b> 只沾到边</span>"
                 "<span><b>L0</b> 找不到证据</span>"
                 "<span>权重按面试中的区分度定，见 kb/role_profiles/</span>"
                 "</div></div>")

    # 与 JD 的匹配度
    if rep.requirements:
        o.append("<h2>与这个 JD 的匹配度</h2>")
    o.append("<div class='card hero'>")
    o.append(f"<div class='dial' style='background:{_dial_color(rep.score, gate)}'>"
             f"<div><b>{rep.score:.0f}</b><span>匹配度</span></div></div>")
    o.append(f"<div style='flex:1;min-width:250px'><div class='verdict'>{e(rep.verdict)}</div>"
             f"<div class='advice'>{e(rep.metrics.get('建议', ''))}</div></div></div>")

    o.append("<div class='subs'>")
    for k, v in rep.sub_scores.items():
        o.append(f"<div class='sub'><i>{e(k)}</i><b>{v:.0f}</b>"
                 f"<div class='bar'><i style='width:{max(0, min(100, v)):.0f}%'></i></div></div>")
    o.append("</div>")

    # 硬性门槛
    if gate:
        o.append("<h2>硬性门槛</h2><div class='card'>")
        o.append("<div style='color:#B4232B;font-weight:650;margin-bottom:6px'>"
                 "以下门槛在简历中没有体现，简历层面大概率过不了筛，先解决这些：</div>")
        for g in rep.hard_gate_failures:
            o.append(f"<div class='quote'>{e(g)}</div>")
        o.append("</div>")

    # 卡点
    o.append("<h2>最卡的 5 件事</h2>")
    if rep.blockers:
        o.append("<div class='card'><table><tr><th style='width:44%'>JD 要求</th>"
                 "<th>覆盖</th><th>类型</th><th>为什么卡</th></tr>")
        for b in rep.blockers:
            label, fg, bg = FIX.get(b["fixability"], FIX["UNKNOWN"])
            o.append(f"<tr><td>{e(b['req'])}</td>"
                     f"<td class='mono'>{b['level']} · {b['strength']:.2f}</td>"
                     f"<td>{_tag(label, fg, bg)}</td>"
                     f"<td>{e(b['why'])}</td></tr>")
        o.append("</table></div>")
        o.append("<div class='card' style='font-size:13.5px;color:#5A6672'>"
                 f"{_tag('做过但没写', *FIX['FIXABLE_NOW'][1:])}立刻能补　"
                 f"{_tag('写了但看不出来', *FIX['REWRITE_ONLY'][1:])}改写即可　"
                 f"{_tag('没做过', *FIX['NEED_EXPERIENCE'][1:])}需要补经历"
                 "</div>")
    else:
        o.append("<div class='card empty'>没有提供 JD，跳过匹配度分析。</div>")

    # 问题清单
    for sev in ("fatal", "important", "suggestion"):
        items = [i for i in rep.issues if i.severity == sev]
        if not items:
            continue
        name, fg, bg = SEV[sev]
        o.append(f"<h2>{name}问题 · {len(items)} 条</h2><div class='card'>")
        for i in items:
            o.append(f"<div class='issue' style='border-color:{fg}'>"
                     f"<div class='t'>{_tag(i.id, fg, bg)}{e(i.title)}"
                     f"<span style='color:#5A6672;font-weight:400'>　{e(i.detail)}</span></div>")
            if i.quote:
                o.append(f"<div class='quote'>{e(i.quote)}</div>")
            if i.interviewer_view:
                o.append(f"<div class='view'>面试官会怎么看：{e(i.interviewer_view)}</div>")
            if i.fix_hint:
                o.append(f"<div class='hint'>怎么改：{e(i.fix_hint)}</div>")
            o.append("</div>")
        o.append("</div>")

    # 改写建议
    if rep.suggestions:
        o.append("<h2>可直接替换的改写</h2><div class='card'>")
        for s in rep.suggestions:
            color = {"A": "#1F7A4D", "B": "#2C6E9B", "C": "#B26A00"}[s.state]
            label = {"A": "事实改写 · 可直接采纳", "B": "结构重组 · 不改一个字",
                     "C": "待确认 · 需要你补信息"}[s.state]
            o.append(f"<div class='issue' style='border-color:{color}'>"
                     f"{_tag(label, color, '#F4F7F9')}")
            o.append(f"<div class='quote'>原句：{e(s.before)}</div>")
            o.append(f"<div class='quote' style='border-style:solid;background:#F1F8F3'>"
                     f"改写：{e(s.after)}</div>")
            o.append(f"<div class='view'>为什么：{e(s.why)}</div>")
            if s.question:
                o.append(f"<div class='hint'>需要你回答：{e(s.question)}</div>")
            if not s.guard_passed:
                o.append(f"<div class='view' style='color:#B4232B'>"
                         f"FactGuard 拦截：{e(s.guard_note)}</div>")
            o.append("</div>")
        o.append("</div>")

    # 待确认追问
    if rep.questions:
        o.append("<h2>需要你回答的问题</h2><div class='card'>")
        o.append("<div style='color:#5A6672;font-size:13.5px;margin-bottom:8px'>"
                 "按回答后能提分多少排序。答完这些，上面黄色的改写才能落地。</div><ol>")
        for q in rep.questions:
            o.append(f"<li style='margin:6px 0'>{e(q)}</li>")
        o.append("</ol></div>")

    # 结构指标
    o.append("<h2>结构指标</h2><div class='grid'>")
    for k, v in rep.metrics.items():
        if k in ("建议",):
            continue
        if isinstance(v, float):
            v = f"{v:.0%}" if 0 <= v <= 1 and "密度" in k or "占比" in k else v
        o.append(f"<div class='kv'><i>{e(str(k))}</i><b>{e(str(v))}</b></div>")
    o.append("</div>")

    o.append("<div class='note'><b>关于这份报告</b><br>"
             "本工具只做表达优化和匹配诊断，不会也不能替你创造经历。"
             "所有标为「待确认」的位置，需要你填入真实数据。"
             "简历里写下的每一个数字，你都要能在面试中讲清它的口径、基线和你的具体贡献。"
             "</div>")

    o.append("</div>")
    return "".join(o)


def dump_json(rep: Report, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rep.to_dict(), f, ensure_ascii=False, indent=2)
