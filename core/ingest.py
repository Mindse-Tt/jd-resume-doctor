# -*- coding: utf-8 -*-
"""把 docx / pdf / md 读成带定位坐标的文本块。

只做读取，不做语义判断。定位坐标必须在这里建立——事后靠字符串搜索定位会因
重复文本定错行。
"""
import os
import re
import subprocess
from dataclasses import dataclass

from .models import Locator


@dataclass
class Block:
    index: int
    text: str
    locator: Locator
    bold_prefix: str = ""   # 段首连续加粗的文字，用作 label
    is_table_row: bool = False


# ---------- docx ----------

def _para_text(p) -> str:
    return "".join(r.text for r in p.runs) or p.text


def _bold_prefix(p) -> str:
    """取段首连续加粗 run 的文字，用来识别 '知识体系与检索策略：' 这类标签。"""
    out = []
    for r in p.runs:
        if r.text.strip() == "":
            if out:
                out.append(r.text)
            continue
        if r.bold:
            out.append(r.text)
        else:
            break
    return "".join(out).strip()


def read_docx(path: str) -> tuple[list[Block], dict]:
    import docx
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    doc = docx.Document(path)
    blocks: list[Block] = []
    meta = {"has_textbox": False, "has_multicol": False,
            "table_para_ratio": 0.0, "styles": set()}

    body_children = list(doc.element.body.iterchildren())
    n_para, n_table_para = 0, 0
    bi = 0
    for b_index, child in enumerate(body_children):
        tag = child.tag.split("}")[1]
        if tag == "p":
            par = Paragraph(child, doc)
            txt = _para_text(par).strip()
            if not txt:
                continue
            meta["styles"].add(par.style.name)
            blocks.append(Block(bi, txt,
                                Locator("para", b_index, len(blocks)),
                                _bold_prefix(par)))
            bi += 1
            n_para += 1
        elif tag == "tbl":
            tb = Table(child, doc)
            for ri, row in enumerate(tb.rows):
                cells = [c.text.strip() for c in row.cells]
                # 合并单元格会重复文本，去重后再拼
                dedup, seen = [], set()
                for c in cells:
                    if c and c not in seen:
                        dedup.append(c)
                        seen.add(c)
                line = "  |  ".join(dedup)
                if not line:
                    continue
                blocks.append(Block(bi, line,
                                    Locator("table", b_index, -1, ri, 0),
                                    is_table_row=True))
                bi += 1
                n_para += 1
                n_table_para += 1

    xml = child_xml(path)
    meta["has_textbox"] = "w:txbxContent" in xml
    meta["has_multicol"] = bool(re.search(r'<w:cols[^>]*w:num="([2-9])', xml))
    meta["table_para_ratio"] = (n_table_para / n_para) if n_para else 0.0
    meta["styles"] = sorted(meta["styles"])
    return blocks, meta


def child_xml(path: str) -> str:
    import zipfile
    with zipfile.ZipFile(path) as z:
        return z.read("word/document.xml").decode("utf-8", "ignore")


# ---------- pdf ----------

def read_pdf(path: str) -> tuple[list[Block], dict]:
    """只读不改。PDF 一律不做回写。"""
    try:
        out = subprocess.run(["pdftotext", "-layout", path, "-"],
                             capture_output=True, check=True).stdout
    except (FileNotFoundError, subprocess.CalledProcessError) as e:
        raise RuntimeError("需要 pdftotext（brew install poppler）来解析 PDF") from e
    text = out.decode("utf-8", "ignore")
    blocks = []
    for i, line in enumerate(l.strip() for l in text.splitlines()):
        if line:
            blocks.append(Block(len(blocks), re.sub(r"\s{2,}", "  |  ", line),
                                Locator("pdf", i)))
    return blocks, {"has_textbox": False, "has_multicol": False,
                    "table_para_ratio": 0.0, "styles": []}


# ---------- md / txt ----------

MD_LEAD = re.compile(r"^\s*(?:#{1,6}\s|[-*+●•·]\s|\d{1,2}[.、)]\s)")


def read_md(path: str) -> tuple[list[Block], dict]:
    """续行要合并回上一条。Markdown 里一条要点常换行续写，
    按行切会把「因此…而非…」这类因果论述劈成两条，判据全废。"""
    text = open(path, encoding="utf-8").read()
    raw_lines = [l.rstrip() for l in text.splitlines()]

    merged: list[tuple[int, str]] = []
    for i, line in enumerate(raw_lines):
        s = line.strip()
        if not s:
            continue
        is_new = bool(MD_LEAD.match(line)) or not merged
        # 无项目符号、有缩进、且上一条不是标题 → 视为续行
        if not is_new and line[:1] in " \t" and not merged[-1][1].startswith("#"):
            merged[-1] = (merged[-1][0], merged[-1][1] + s)
        else:
            merged.append((i, s))

    blocks = []
    for i, s in merged:
        bold = ""
        m = re.match(r"^[#\-*●•·\s]*\*\*(.+?)\*\*", s)
        if m:
            bold = m.group(1)
        # 剥掉 markdown 标题符号——它是格式不是内容，
        # 留着会让「## 实习经历」认不出是小节标题
        s = re.sub(r"^#{1,6}\s*", "", s)
        blocks.append(Block(len(blocks), s, Locator("md", i), bold))
    return blocks, {"has_textbox": False, "has_multicol": False,
                    "table_para_ratio": 0.0, "styles": []}


READERS = {".docx": read_docx, ".pdf": read_pdf, ".md": read_md, ".txt": read_md}


def read(path: str) -> tuple[list[Block], dict]:
    ext = os.path.splitext(path)[1].lower()
    if ext not in READERS:
        raise ValueError(f"不支持的格式：{ext}（支持 docx / pdf / md / txt）")
    return READERS[ext](path)


def editability(path: str, meta: dict) -> tuple[bool, str]:
    """能否安全地做 run 级局部替换。不能就坦率降级，不硬改。"""
    if not path.lower().endswith((".docx", ".md", ".txt")):
        return False, "PDF 不可安全编辑，只输出对照表"
    if meta.get("has_textbox"):
        return False, "简历使用了文本框，python-docx 遍历不到，只输出对照表"
    if meta.get("has_multicol"):
        return False, "简历使用了多栏排版，ATS 解析也有风险，只输出对照表"
    return True, ""
