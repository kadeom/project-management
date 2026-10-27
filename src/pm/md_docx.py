"""Markdown → .docx для методических документов и отчётов.

Модуль намеренно поддерживает только тот Markdown, который используется в
``docs/guidelines/`` и ``srs/``: заголовки, абзацы, списки, таблицы, цитаты,
блоки кода, разрывы страниц и простые inline-выделения. Этого достаточно,
чтобы держать содержание в diff-пригодном виде, а готовый ``.docx`` собирать
одной командой.

Формат блоков совпадает с ``pm.report``/``pm.report_infosec``:
``("h1"|"h2"|"h3"|"p"|"li"|"table"|"shot", ...)``. Поэтому генераторы могут
переиспользовать один рендер.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

_FRONT_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)
_INLINE_RE = re.compile(r"(\*\*.+?\*\*|\*[^*\n]+?\*|`[^`\n]+?`)")


def load_markdown(path: str | Path) -> tuple[dict, str]:
    """Прочитать Markdown с YAML front matter.

    Returns:
        (метаданные, тело без front matter). Если front matter нет, метаданные пустые.
    """
    text = Path(path).read_text(encoding="utf-8")
    m = _FRONT_RE.match(text)
    if not m:
        return {}, text
    meta = yaml.safe_load(m[1]) or {}
    if not isinstance(meta, dict):
        raise ValueError("front matter должен быть YAML-словарём")
    return meta, text[m.end():]


def parse(text: str) -> list[tuple]:
    """Разобрать поддерживаемый Markdown в список блоков."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    blocks: list[tuple] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        if stripped == "<!-- pagebreak -->":
            blocks.append(("pagebreak",))
            i += 1
            continue

        if stripped.startswith("```"):
            i += 1
            code: list[str] = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code.append(lines[i])
                i += 1
            i += 1
            blocks.append(("code", "\n".join(code)))
            continue

        m = re.match(r"^(#{1,4})\s+(.*)$", stripped)
        if m:
            blocks.append(("h", len(m[1]), m[2].strip()))
            i += 1
            continue

        if stripped.startswith(">"):
            quote: list[str] = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote.append(lines[i].strip()[1:].strip())
                i += 1
            blocks.append(("quote", " ".join(x for x in quote if x)))
            continue

        if stripped.startswith("|") and i + 1 < len(lines) and _is_table_sep(lines[i + 1]):
            head = _cells(stripped)
            i += 2
            rows: list[list[str]] = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(_cells(lines[i].strip()))
                i += 1
            blocks.append(("table", head, rows))
            continue

        if re.match(r"^[-*+]\s+", stripped):
            items: list[str] = []
            while i < len(lines) and re.match(r"^[-*+]\s+", lines[i].strip()):
                item = re.sub(r"^[-*+]\s+", "", lines[i].strip())
                i += 1
                while i < len(lines) and lines[i].startswith(("  ", "\t")) and lines[i].strip():
                    item += " " + lines[i].strip()
                    i += 1
                items.append(item)
            blocks.append(("ul", items))
            continue

        if re.match(r"^\d+[.)]\s+", stripped):
            items = []
            while i < len(lines) and re.match(r"^\d+[.)]\s+", lines[i].strip()):
                item = re.sub(r"^\d+[.)]\s+", "", lines[i].strip())
                i += 1
                while i < len(lines) and lines[i].startswith(("  ", "\t")) and lines[i].strip():
                    item += " " + lines[i].strip()
                    i += 1
                items.append(item)
            blocks.append(("ol", items))
            continue

        para: list[str] = [stripped]
        i += 1
        while i < len(lines):
            nxt = lines[i].strip()
            if (not nxt or nxt.startswith(("#", ">", "```", "|", "<!--"))
                    or re.match(r"^[-*+]\s+", nxt) or re.match(r"^\d+[.)]\s+", nxt)):
                break
            para.append(nxt)
            i += 1
        blocks.append(("p", " ".join(para)))
    return blocks


def _is_table_sep(line: str) -> bool:
    cells = _cells(line.strip())
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", c) for c in cells)


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _add_inline(par, text: str) -> None:
    """Добавить текст с **жирным**, *курсивом* и `кодом`."""
    pos = 0
    for m in _INLINE_RE.finditer(text):
        if m.start() > pos:
            par.add_run(text[pos:m.start()])
        token = m.group(0)
        if token.startswith("**"):
            par.add_run(token[2:-2]).bold = True
        elif token.startswith("`"):
            run = par.add_run(token[1:-1])
            run.font.name = "Consolas"
        else:
            par.add_run(token[1:-1]).italic = True
        pos = m.end()
    if pos < len(text):
        par.add_run(text[pos:])


def _add_page_number(par) -> None:
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    run = par.add_run()
    fld_begin = OxmlElement("w:fldChar")
    fld_begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = "PAGE"
    fld_end = OxmlElement("w:fldChar")
    fld_end.set(qn("w:fldCharType"), "end")
    run._r.append(fld_begin)
    run._r.append(instr)
    run._r.append(fld_end)


def _add_toc(doc) -> None:
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    p = doc.add_paragraph()
    run = p.add_run()
    fld_begin = OxmlElement("w:fldChar")
    fld_begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = 'TOC \\o "1-3" \\h \\z \\u'
    fld_sep = OxmlElement("w:fldChar")
    fld_sep.set(qn("w:fldCharType"), "separate")
    txt = OxmlElement("w:t")
    txt.text = "Оглавление обновляется в Word: Ссылки → Обновить таблицу."
    fld_end = OxmlElement("w:fldChar")
    fld_end.set(qn("w:fldCharType"), "end")
    for el in (fld_begin, instr, fld_sep, txt, fld_end):
        run._r.append(el)


def render_docx(blocks: list[tuple], path: str | Path, meta: dict | None = None,
                title_page: bool = True, toc: bool = True) -> Path:
    """Отрендерить блоки в .docx с титульным листом и оглавлением."""
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Cm, Pt, RGBColor

    meta = meta or {}
    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21), Cm(29.7)
    sec.left_margin = sec.right_margin = Cm(2)
    sec.top_margin = sec.bottom_margin = Cm(2)
    st = doc.styles["Normal"]
    st.font.name, st.font.size = "Times New Roman", Pt(12)
    st.paragraph_format.space_after = Pt(4)
    st.paragraph_format.line_spacing = 1.15

    for name, size in (("Heading 1", 16), ("Heading 2", 14), ("Heading 3", 13), ("Heading 4", 12)):
        h = doc.styles[name]
        h.font.name = "Times New Roman"
        h.font.size = Pt(size)
        h.font.bold = True
        h.font.color.rgb = RGBColor(0, 0, 0)

    if title_page:
        t = doc.add_paragraph()
        t.alignment = WD_ALIGN_PARAGRAPH.CENTER
        t.paragraph_format.space_before = Pt(90)
        t.add_run(str(meta.get("organization", "")) + "\n\n").bold = True
        t.add_run(str(meta.get("title", "Документ")) + "\n").bold = True
        t.add_run(str(meta.get("subtitle", "")) + "\n\n")
        for key in ("discipline", "author", "group", "version", "date"):
            if meta.get(key):
                t.add_run(f"{meta[key]}\n")
        doc.add_page_break()
        if toc:
            doc.add_heading("Содержание", level=1)
            _add_toc(doc)
            doc.add_page_break()

    for b in blocks:
        kind = b[0]
        if kind == "h":
            doc.add_heading(b[2], level=min(int(b[1]), 4))
        elif kind == "p":
            _add_inline(doc.add_paragraph(), b[1])
        elif kind == "ul":
            for item in b[1]:
                _add_inline(doc.add_paragraph(style="List Bullet"), item)
        elif kind == "ol":
            for item in b[1]:
                _add_inline(doc.add_paragraph(style="List Number"), item)
        elif kind == "quote":
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Cm(1)
            r = p.add_run(b[1])
            r.italic = True
        elif kind == "code":
            for line in b[1].split("\n"):
                p = doc.add_paragraph()
                p.paragraph_format.left_indent = Cm(0.5)
                r = p.add_run(line or " ")
                r.font.name = "Consolas"
                r.font.size = Pt(9)
        elif kind == "table":
            head, rows = b[1], b[2]
            tbl = doc.add_table(rows=1, cols=len(head))
            tbl.style = "Table Grid"
            for j, h in enumerate(head):
                cell = tbl.rows[0].cells[j]
                cell.text = ""
                cell.paragraphs[0].add_run(str(h)).bold = True
            for row in rows:
                cells = tbl.add_row().cells
                for j, val in enumerate(row[:len(head)]):
                    cells[j].text = ""
                    _add_inline(cells[j].paragraphs[0], str(val))
            for row in tbl.rows:
                for cell in row.cells:
                    for par in cell.paragraphs:
                        par.paragraph_format.space_after = Pt(0)
                        for run in par.runs:
                            run.font.size = Pt(9)
            doc.add_paragraph()
        elif kind == "pagebreak":
            doc.add_page_break()
        elif kind == "shot":
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            r = p.add_run(str(b[1]))
            r.italic = True
            r.font.color.rgb = RGBColor(0x80, 0x80, 0x80)
        else:
            raise ValueError(f"неизвестный блок: {kind!r}")

    footer = sec.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _add_page_number(footer)

    cp = doc.core_properties
    cp.title = str(meta.get("title", ""))
    cp.subject = str(meta.get("subtitle", ""))
    cp.author = str(meta.get("author", ""))

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(path)
    return path


def render_markdown(blocks: list[tuple]) -> str:
    """Обратное преобразование блоков в Markdown (для вычитки и diff)."""
    out: list[str] = []
    for b in blocks:
        kind = b[0]
        if kind == "h":
            out.append("#" * int(b[1]) + " " + b[2])
        elif kind == "p":
            out.append(b[1])
        elif kind == "ul":
            out += ["- " + x for x in b[1]]
        elif kind == "ol":
            out += [f"{i}. {x}" for i, x in enumerate(b[1], start=1)]
        elif kind == "quote":
            out.append("> " + b[1])
        elif kind == "code":
            out += ["```", b[1], "```"]
        elif kind == "table":
            out.append("| " + " | ".join(b[1]) + " |")
            out.append("|" + "---|" * len(b[1]))
            out += ["| " + " | ".join(map(str, r)) + " |" for r in b[2]]
        elif kind == "pagebreak":
            out.append("<!-- pagebreak -->")
        elif kind == "shot":
            out.append(f"> 📷 {b[1]}")
        out.append("")
    return "\n".join(out)
