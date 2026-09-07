# -*- coding: utf-8 -*-
"""文本块 → 分节 / 经历 / bullet，并同步构建 FactLedger。"""
import re

from .ingest import Block, editability, read
from .models import Bullet, Experience, FactLedger, Locator, Metric, Resume, Section

SECTION_PATTERNS = [
    ("edu",        r"教育(背景|经历|信息)|学历"),
    ("experience", r"(实习|工作|职业)(经历|经验)|Experience"),
    ("project",    r"(项目|科研|作品|实践)(经历|经验|与.*实践)?|AI\s*产品|Project"),
    ("skill",      r"(专业|个人|核心)?(能力|技能)|Skills?"),
    ("award",      r"(竞赛|获奖|荣誉|奖项)(经历)?|Awards?"),
    ("other",      r"自我评价|个人评价|求职意向|兴趣"),
]

DATE_RANGE = re.compile(
    r"(20\d{2}[./\-年]\s*\d{0,2})\s*[.\-—~至到]{1,3}\s*(20\d{2}[./\-年]\s*\d{0,2}|至今|now|present)",
    re.I)

# 成果类线索
OUTCOME_HINT = re.compile(r"提升|下降|降低|增长|减少|提高|达到|实现|上线|覆盖|突破|优化至|→|->")

NUM = re.compile(r"\d+(?:\.\d+)?\s*(?:%|pp|万|亿|千|人|次|天|小时|分钟|秒|s|倍|条|个|元|W|w)?")
ARROW = re.compile(r"\d+(?:\.\d+)?\s*%?\s*(?:→|->|至|到)\s*\d+(?:\.\d+)?\s*%?")
ENTITY = re.compile(
    r"[A-Za-z][A-Za-z0-9+#./\-]{1,24}|"
    r"[一-龥]{2,10}(?=大学|学院|公司|集团|事业群|科技|网络|银行|研究院)")

BULLET_LEAD = re.compile(r"^[\s]*[●•·◦▪‣\-–—*·]\s*|^\s*\d{1,2}[.、)]\s*")
# 项目标题行：短、无句号、带分隔符或以序号开头
TITLE_LINE = re.compile(r"^\s*\d{1,2}[.、)]\s*|[｜|]")
# 抬头信息行：联系方式、求职意向
HEAD_LINE = re.compile(r"^(电话|手机|邮箱|邮件|微信|求职意向|意向岗位|Github|GitHub)\s*[：:]|"
                       r"1[3-9]\d{9}|[\w.\-]+@[\w.\-]+")
LABEL_COLON = re.compile(r"^[\[【]?([^：:\[\]【】]{2,20})[\]】]?\s*[：:]")


def _section_kind(text: str) -> str | None:
    t = text.strip()
    if len(t) > 16 or "|" in t:
        return None
    for kind, pat in SECTION_PATTERNS:
        if re.fullmatch(rf"\s*(?:{pat})\s*[/／·]?\s*[A-Za-z ]*\s*", t):
            return kind
    return None


def _split_metrics(text: str) -> list[Metric]:
    metrics: list[Metric] = []
    for m in ARROW.finditer(text):
        metrics.append(Metric(raw=m.group(0), kind="range", has_baseline=True))
    consumed = " ".join(m.raw for m in metrics)
    for m in NUM.finditer(text):
        tok = m.group(0).strip()
        if tok in consumed or not re.search(r"\d", tok):
            continue
        kind = "relative" if "%" in tok or "倍" in tok else "absolute"
        metrics.append(Metric(raw=tok, kind=kind))
    return metrics


def _verb(text: str, lexicon: dict) -> tuple[str, int]:
    body = LABEL_COLON.sub("", text).strip()
    for level in (3, 2, 1):
        for v in lexicon["verbs"][f"L{level}"]:
            if v in body[:40]:
                return v, level
    return "", 0


def build_facts(blocks: list[Block]) -> FactLedger:
    """事实台账：简历里出现过的数字、专有名词、时间段。改写时的唯一真源。"""
    f = FactLedger()
    seen_n, seen_e, seen_p = set(), set(), set()
    for b in blocks:
        for m in NUM.finditer(b.text):
            tok = m.group(0).strip()
            if tok and tok not in seen_n:
                seen_n.add(tok)
                f.numbers.append(tok)
        for m in ENTITY.finditer(b.text):
            tok = m.group(0).strip()
            if len(tok) > 1 and tok not in seen_e:
                seen_e.add(tok)
                f.entities.append(tok)
        for m in DATE_RANGE.finditer(b.text):
            tok = m.group(0).strip()
            if tok not in seen_p:
                seen_p.add(tok)
                f.periods.append(tok)
    return f


def parse(path: str, lexicon: dict) -> Resume:
    blocks, meta = read(path)
    ok, why = editability(path, meta)
    r = Resume(path=path, editable=ok, editable_reason=why,
               raw_text="\n".join(b.text for b in blocks))
    r.facts = build_facts(blocks)

    cur_section: Section | None = None
    cur_exp: Experience | None = None
    section_start = 0

    for b in blocks:
        kind = _section_kind(b.text)
        if kind:
            if cur_section:
                cur_section.block_range = (section_start, b.index)
                r.sections.append(cur_section)
            cur_section = Section(title=b.text.strip(), kind=kind)
            section_start = b.index
            cur_exp = None
            continue

        sec_kind = cur_section.kind if cur_section else "other"
        sec_title = cur_section.title if cur_section else ""

        # 经历抬头：表格行，或含时间区间的短行
        is_header = sec_kind in ("experience", "project", "edu") and len(b.text) < 90 and (
            DATE_RANGE.search(b.text) or
            (b.is_table_row and b.text.count("|") >= 1))
        if is_header:
            parts = [p.strip() for p in b.text.split("|") if p.strip()]
            period = ""
            m = DATE_RANGE.search(b.text)
            if m:
                period = m.group(0)
            parts = [p for p in parts if period not in p] or parts
            cur_exp = Experience(
                id=f"X-{len(r.experiences) + 1:02d}",
                org=parts[0] if parts else b.text[:24],
                role=parts[1] if len(parts) > 1 else "",
                period_raw=period, section=sec_title)
            r.experiences.append(cur_exp)
            continue

        # 其余正文视为 bullet
        text = BULLET_LEAD.sub("", b.text).strip()
        if len(text) < 6:
            continue
        # 抬头信息行不进内容分析（但仍留在 raw_text 里供 META 规则用）
        if HEAD_LINE.search(text) and len(text) < 90:
            continue
        is_title = (len(text) < 50 and "。" not in text
                    and bool(TITLE_LINE.search(b.text)))
        label = b.bold_prefix.rstrip("：: ") if b.bold_prefix else ""
        if not label:
            m = LABEL_COLON.match(text)
            if m:
                label = m.group(1)
        verb, lvl = _verb(text, lexicon)
        metrics = _split_metrics(text)
        bu = Bullet(
            id=f"E-{len(r.bullets) + 1:02d}", raw=text, locator=b.locator,
            experience_id=cur_exp.id if cur_exp else "", section=sec_title,
            label=label, verb=verb, verb_level=lvl, metrics=metrics,
            has_number=bool(metrics), char_len=len(text),
            is_outcome=bool(OUTCOME_HINT.search(text)) and not is_title,
            is_title=is_title,
            empty_words=[w for w in lexicon["empty_words"] if w in text],
            ai_phrases=[p for p in lexicon["ai_phrases"] if p in text],
            terms=sorted({m.group(0) for m in ENTITY.finditer(text)
                          if re.match(r"[A-Za-z]", m.group(0))}),
        )
        r.bullets.append(bu)
        if cur_exp:
            cur_exp.bullet_ids.append(bu.id)

    if cur_section:
        cur_section.block_range = (section_start, blocks[-1].index if blocks else 0)
        r.sections.append(cur_section)

    # 姓名：第一块通常是姓名
    if blocks:
        head = blocks[0].text.replace(" ", "")
        if 2 <= len(head) <= 5 and re.fullmatch(r"[一-龥]+", head):
            r.name = head
    return r
