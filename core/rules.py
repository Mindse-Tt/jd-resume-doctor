# -*- coding: utf-8 -*-
"""确定性检测器。能用规则的绝不用 LLM——规则零成本、可单测、结果稳定，
是整份报告可信度的地基。语义类判断交给 Skill 层。
"""
import re

from .models import Issue, Resume

REGISTRY = {}


def rule(rid):
    def deco(fn):
        REGISTRY[rid] = fn
        return fn
    return deco


def content_bullets(r: Resume):
    """参与内容类规则的要点：排除项目标题行。"""
    return [b for b in r.bullets if not b.is_title]


def _issue(kb, rid, *, detail="", bullet=None, quote="", conf=1.0) -> Issue:
    k = kb[rid]
    return Issue(id=rid, category=k["category"], severity=k["severity"],
                 title=k["title"], detail=detail,
                 bullet_id=bullet.id if bullet else "",
                 locator_key=bullet.locator.key() if bullet else "",
                 quote=quote or (bullet.raw[:70] if bullet else ""),
                 interviewer_view=k.get("interviewer_view", ""),
                 fix_hint=k.get("fix_hint", ""), confidence=conf)


# ---------- 真实性 ----------

@rule("AUTH-01")
def auth_01(r: Resume, kb, lex):
    out = []
    for b in r.bullets:
        for m in re.finditer(r"(\d+(?:\.\d+)?)\s*(%|倍)", b.raw):
            v = float(m.group(1))
            if (m.group(2) == "%" and v >= 300) or (m.group(2) == "倍" and v >= 10):
                out.append(_issue(kb, "AUTH-01", bullet=b,
                                  detail=f"出现 {m.group(0)}，量级不合常理"))
                break
    return out


@rule("AUTH-02")
def auth_02(r: Resume, kb, lex):
    out = []
    for b in content_bullets(r):
        if b.verb_level != 3:
            continue
        has_method = bool(re.search(r"通过|基于|采用|以.{1,12}(方式|方法)|用\w|设计|拆|融合", b.raw))
        if not (has_method and b.has_number):
            miss = []
            if not has_method:
                miss.append("方法")
            if not b.has_number:
                miss.append("结果数字")
            out.append(_issue(kb, "AUTH-02", bullet=b,
                              detail=f"用了强动词「{b.verb}」但缺少：{'、'.join(miss)}"))
    return out


@rule("AUTH-04")
def auth_04(r: Resume, kb, lex):
    def norm(p):
        m = re.findall(r"20\d{2}", p)
        return [int(x) for x in m]
    spans = []
    for e in r.experiences:
        if e.section and "教育" in e.section:
            continue
        ys = norm(e.period_raw)
        if len(ys) >= 2:
            spans.append((ys[0], ys[1], e))
        elif len(ys) == 1 and re.search(r"至今|now|present", e.period_raw, re.I):
            spans.append((ys[0], 9999, e))
    out = []
    for i in range(len(spans)):
        for j in range(i + 1, len(spans)):
            a, b = spans[i], spans[j]
            if a[0] < b[1] and b[0] < a[1] and a[0] != b[0]:
                out.append(_issue(kb, "AUTH-04",
                                  detail=f"「{a[2].org}」{a[2].period_raw} 与 "
                                         f"「{b[2].org}」{b[2].period_raw} 时间重叠",
                                  quote=f"{a[2].org} / {b[2].org}"))
    return out[:3]


@rule("AUTH-06")
def auth_06(r: Resume, kb, lex):
    out = []
    for b in content_bullets(r):
        rel = [m for m in b.metrics if m.kind in ("relative", "range")]
        if not rel:
            continue
        has_baseline = any(m.has_baseline for m in rel)
        has_scope = bool(re.search(r"评测集|样本|标注|口径|条|人|基线|Top\s*\d|环比|同比", b.raw))
        if not (has_baseline and has_scope):
            out.append(_issue(kb, "AUTH-06", bullet=b,
                              detail=f"{len(rel)} 个比例型指标缺少基线或口径说明"))
    return out


@rule("AUTH-08")
def auth_08(r: Resume, kb, lex):
    out = []
    for b in content_bullets(r):
        if re.search(r"精通|熟练掌握|深入理解", b.raw):
            out.append(_issue(kb, "AUTH-08", bullet=b,
                              detail="自评式措辞，建议改成具体做过什么"))
    return out


# ---------- 量化 ----------

@rule("QUANT-01")
def quant_01(r: Resume, kb, lex):
    return [_issue(kb, "QUANT-01", bullet=b, detail="成果句但通篇无数字")
            for b in content_bullets(r) if b.is_outcome and not b.has_number]


@rule("QUANT-03")
def quant_03(r: Resume, kb, lex):
    out = []
    for b in content_bullets(r):
        pct = [m for m in b.metrics if m.kind == "relative" and not m.has_baseline]
        absn = [m for m in b.metrics if m.kind == "absolute"]
        if pct and not absn:
            out.append(_issue(kb, "QUANT-03", bullet=b,
                              detail=f"只有 {pct[0].raw}，没有基数"))
    return out


@rule("QUANT-04")
def quant_04(r: Resume, kb, lex):
    out = []
    for b in content_bullets(r):
        for w in lex["weak_metrics"]:
            if re.search(rf"{re.escape(w)}\s*\d|\d+\s*[+份个篇]?\s*{re.escape(w)}", b.raw):
                out.append(_issue(kb, "QUANT-04", bullet=b,
                                  detail=f"「{w}」的数量属于过程指标"))
                break
    return out


@rule("QUANT-05")
def quant_05(r: Resume, kb, lex):
    outs = [b for b in content_bullets(r) if b.is_outcome]
    if len(outs) < 3:
        return []
    dens = sum(1 for b in outs if b.has_number) / len(outs)
    if dens < 0.4:
        return [_issue(kb, "QUANT-05",
                       detail=f"成果句量化密度仅 {dens:.0%}（健康线 ≥ 50%）",
                       quote=f"{len(outs)} 条成果句中只有 {sum(1 for b in outs if b.has_number)} 条带数字")]
    return []


# ---------- 归因 ----------

ROLE_WORDS = r"独立负责|主导|牵头|作为.{0,6}负责|参与|协助|配合|支持|担任"


@rule("ATTR-01")
def attr_01(r: Resume, kb, lex):
    out = []
    for e in r.experiences:
        if "教育" in (e.section or ""):
            continue
        text = " ".join(r.bullet(b).raw for b in e.bullet_ids if r.bullet(b))
        if not text:
            continue
        if not re.search(ROLE_WORDS, text[:200]):
            out.append(_issue(kb, "ATTR-01",
                              detail=f"「{e.org}」这段没写清你是主导还是参与",
                              quote=e.org))
    return out


@rule("ATTR-03")
def attr_03(r: Resume, kb, lex):
    out = []
    for b in content_bullets(r):
        if not b.is_outcome:
            continue
        if not re.search(r"通过|基于|采用|以.{1,12}(方式|方法)|因为|由于|所以|——|故|设计|拆解|融合", b.raw):
            out.append(_issue(kb, "ATTR-03", bullet=b,
                              detail="有动作有结果，但看不到方法或理由"))
    return out


# ---------- 表达 ----------

@rule("TERM-03")
def term_03(r: Resume, kb, lex):
    return [_issue(kb, "TERM-03", bullet=b,
                   detail="出现大词：" + "、".join(b.empty_words))
            for b in content_bullets(r) if len(b.empty_words) >= 2]


@rule("TERM-04")
def term_04(r: Resume, kb, lex):
    return [_issue(kb, "TERM-04", bullet=b,
                   detail="模板腔：" + "、".join(b.ai_phrases))
            for b in content_bullets(r) if b.ai_phrases]


@rule("TERM-05")
def term_05(r: Resume, kb, lex):
    weak = [b for b in content_bullets(r) if b.verb_level == 1]
    cb = content_bullets(r)
    if cb and len(weak) / len(cb) > 0.3:
        return [_issue(kb, "TERM-05",
                       detail=f"{len(weak)}/{len(cb)} 条以弱动词开头（参与/协助/负责日常等）",
                       quote=weak[0].raw[:60])]
    return []


# ---------- 结构 / 语言 / 信息 ----------

@rule("STRUCT-03")
def struct_03(r: Resume, kb, lex):
    return [_issue(kb, "STRUCT-03",
                   detail=f"「{e.org}」下有 {len(e.bullet_ids)} 条要点", quote=e.org)
            for e in r.experiences if len(e.bullet_ids) > 6]


@rule("STRUCT-05")
def struct_05(r: Resume, kb, lex):
    n = len(r.raw_text.replace("\n", ""))
    if n > 3600:
        return [_issue(kb, "STRUCT-05",
                       detail=f"正文约 {n} 字，应届生一页纸的容量约 2600-3200 字",
                       quote=f"{n} 字")]
    return []


@rule("LANG-03")
def lang_03(r: Resume, kb, lex):
    out = []
    for b in content_bullets(r):
        for seg in re.split(r"[。；;]", b.raw):
            if len(seg.strip()) > 70:
                out.append(_issue(kb, "LANG-03", bullet=b,
                                  detail=f"存在 {len(seg.strip())} 字长句",
                                  quote=seg.strip()[:70]))
                break
    return out


@rule("META-01")
def meta_01(r: Resume, kb, lex):
    head = r.raw_text[:400]
    out = []
    if not re.search(r"1[3-9]\d{9}", head):
        out.append(_issue(kb, "META-01", detail="没找到手机号", quote=head[:40]))
    m = re.search(r"[\w.\-]+@[\w.\-]+", head)
    if not m:
        out.append(_issue(kb, "META-01", detail="没找到邮箱", quote=head[:40]))
    elif re.match(r"^\d{6,}@", m.group(0)):
        out.append(_issue(kb, "META-01",
                          detail=f"邮箱 {m.group(0)} 是数字账号，建议换成姓名拼音邮箱",
                          quote=m.group(0)))
    return out


@rule("META-02")
def meta_02(r: Resume, kb, lex):
    out = []
    for pat, what in [(r"\d{17}[\dXx]", "身份证号"), (r"婚(否|姻状况)|已婚|未婚", "婚育状况"),
                      (r"籍贯|户口所在地|家庭住址", "住址/籍贯")]:
        m = re.search(pat, r.raw_text)
        if m:
            out.append(_issue(kb, "META-02", detail=f"出现{what}", quote=m.group(0)))
    return out


MAX_PER_RULE = 4


def run_all(resume: Resume, kb: dict, lexicon: dict) -> list[Issue]:
    issues: list[Issue] = []
    for rid, fn in REGISTRY.items():
        if rid not in kb:
            continue
        try:
            found = fn(resume, kb, lexicon)
            if len(found) > MAX_PER_RULE:
                extra = len(found) - MAX_PER_RULE
                found = found[:MAX_PER_RULE]
                found[-1].detail += f"（同类问题另有 {extra} 处，改法相同）"
            issues.extend(found)
        except Exception as e:                       # 单条规则挂掉不该拖垮整份报告
            issues.append(Issue(id=rid, category="引擎", severity="suggestion",
                                title=f"规则 {rid} 执行失败", detail=str(e)))
    order = {"fatal": 0, "important": 1, "suggestion": 2}
    issues.sort(key=lambda i: (order.get(i.severity, 3), i.id))
    return issues
