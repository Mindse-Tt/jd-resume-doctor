# -*- coding: utf-8 -*-
"""全流程共用的数据结构。所有环节只认这些 schema。"""
from dataclasses import dataclass, field, asdict
from typing import Optional, Any


# ---------- 简历侧 ----------

@dataclass
class Locator:
    """回写 docx 用的定位坐标。source 为 'para' 或 'table'。"""
    source: str
    block_index: int
    para_index: int = -1
    row: int = -1
    cell: int = -1

    def key(self) -> str:
        return f"{self.source}:{self.block_index}:{self.para_index}:{self.row}:{self.cell}"


@dataclass
class Metric:
    raw: str
    value: Optional[float] = None
    unit: str = ""
    kind: str = "unknown"       # relative | absolute | range | ratio
    has_baseline: bool = False  # 出现 X→Y 或"由…至…"
    has_period: bool = False    # 出现时间窗口


@dataclass
class Bullet:
    """证据原子。"""
    id: str
    raw: str
    locator: Locator
    experience_id: str = ""
    section: str = ""
    label: str = ""             # "知识体系与检索策略" 这类加粗前缀
    verb: str = ""
    verb_level: int = 0         # 1 弱 / 2 中 / 3 强 / 0 未识别
    metrics: list[Metric] = field(default_factory=list)
    has_number: bool = False
    is_outcome: bool = False    # 是否成果句
    is_title: bool = False      # 项目标题/抬头行，不参与内容类规则
    char_len: int = 0
    empty_words: list[str] = field(default_factory=list)
    ai_phrases: list[str] = field(default_factory=list)
    terms: list[str] = field(default_factory=list)


@dataclass
class Experience:
    id: str
    org: str = ""
    role: str = ""
    period_raw: str = ""
    start: Optional[str] = None
    end: Optional[str] = None
    section: str = ""
    bullet_ids: list[str] = field(default_factory=list)


@dataclass
class Section:
    title: str
    kind: str                   # edu | experience | project | skill | award | other
    block_range: tuple[int, int] = (0, 0)


@dataclass
class FactLedger:
    """只增不改。改写时的唯一事实来源，FactGuard 据此拦截编造。"""
    numbers: list[str] = field(default_factory=list)
    entities: list[str] = field(default_factory=list)
    periods: list[str] = field(default_factory=list)
    user_supplied: list[str] = field(default_factory=list)

    def allows_number(self, token: str) -> bool:
        return token in self.numbers or token in self.user_supplied


@dataclass
class Resume:
    path: str = ""
    name: str = ""
    raw_text: str = ""
    sections: list[Section] = field(default_factory=list)
    experiences: list[Experience] = field(default_factory=list)
    bullets: list[Bullet] = field(default_factory=list)
    facts: FactLedger = field(default_factory=FactLedger)
    editable: bool = True
    editable_reason: str = ""

    def bullet(self, bid: str) -> Optional[Bullet]:
        return next((b for b in self.bullets if b.id == bid), None)


# ---------- JD 侧 ----------

@dataclass
class RequirementAtom:
    id: str
    raw: str                    # 必须是 JD 原文子串
    type: str                   # hard_gate | core_duty | plus | hidden
    dimension: str = ""
    keywords: list[str] = field(default_factory=list)
    weight: float = 0.0
    source: str = "explicit"    # explicit | inferred
    implies: str = ""           # hidden 类的隐含能力


@dataclass
class Coverage:
    req_id: str
    level: str = "L0"           # L3 直接证明 / L2 部分 / L1 可迁移 / L0 无证据
    cited: list[str] = field(default_factory=list)
    strength: float = 0.0
    gap_reason: str = ""
    fixability: str = "UNKNOWN"  # FIXABLE_NOW | REWRITE_ONLY | NEED_EXPERIENCE


# ---------- 问题与建议 ----------

@dataclass
class Issue:
    id: str                     # QUANT-01 这类知识库编号
    category: str
    severity: str               # fatal | important | suggestion
    title: str
    detail: str = ""
    bullet_id: str = ""
    locator_key: str = ""
    quote: str = ""
    interviewer_view: str = ""
    fix_hint: str = ""
    confidence: float = 1.0


@dataclass
class Suggestion:
    bullet_id: str
    state: str                  # A 事实改写 / B 结构重组 / C 待确认空缺
    before: str
    after: str
    why: str
    question: str = ""
    guard_passed: bool = True
    guard_note: str = ""


@dataclass
class Report:
    resume_path: str = ""
    jd_title: str = ""
    verdict: str = ""
    score: float = 0.0
    sub_scores: dict[str, float] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)
    hard_gate_failures: list[str] = field(default_factory=list)
    blockers: list[dict] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)
    coverage: list[Coverage] = field(default_factory=list)
    requirements: list[RequirementAtom] = field(default_factory=list)
    suggestions: list[Suggestion] = field(default_factory=list)
    questions: list[str] = field(default_factory=list)
    profile: dict = field(default_factory=dict)        # 岗位能力模型体检结果
    dimensions: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)
