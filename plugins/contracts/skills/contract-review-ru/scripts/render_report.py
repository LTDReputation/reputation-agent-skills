#!/usr/bin/env python3
"""Render a contract-review conclusion written in Markdown to PDF and/or DOCX.

Standard library only. The agent writes the report as Markdown, then runs:

    python3 render_report.py report.md --pdf "Заключение_….pdf"
    python3 render_report.py protocol.md --docx "Протокол_разногласий_….docx"
    python3 render_report.py report.md --pdf out.pdf --docx out.docx --html out.html

Supported Markdown subset (enough for the report template): headings (#..######),
paragraphs (single newlines are kept as line breaks), pipe tables, bullet and
numbered lists (indent by 2 spaces to nest), > quotes, --- rules, ``` code blocks,
**bold**, *italic*, `code`, [links](url).

Risk levels: a table cell that consists only of «Критический», «Высокий»,
«Средний» or «Низкий» (any case, optional emoji/punctuation), and the value
after «уровень риска:», are rendered as colored badges that keep the word,
so the report stays readable when printed in black and white.

PDF engines, in order (override with --engine):
  1. weasyprint — Python module or CLI, if installed;
  2. headless Chrome / Chromium / Edge / Brave (set CHROME_PATH to force a binary).
     Page numbers need Chrome 131+ (CSS page-margin boxes).

Exit codes: 0 — every requested file written; 2 — no PDF engine available or it
failed (an .html copy is written next to the requested PDF so the report is not
lost); 1 — bad input.
"""

from __future__ import annotations

import argparse
import html
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

# ─── Risk levels ──────────────────────────────────────────────────────────────

# word → (css class, background hex, text hex)
LEVELS = {
    "критический": ("crit", "B71C1C", "FFFFFF"),
    "высокий": ("high", "E65100", "FFFFFF"),
    "средний": ("med", "F9A825", "000000"),
    "низкий": ("low", "2E7D32", "FFFFFF"),
}
_LEVEL_CELL = re.compile(r"^[\W_]*(критический|высокий|средний|низкий)[\W_]*$", re.I)
_LEVEL_INLINE = re.compile(
    r"(уровень риска\s*:?\s*(?:</strong>)?\s*)(критический|высокий|средний|низкий)", re.I
)


def level_of(plain: str) -> str | None:
    m = _LEVEL_CELL.match(plain.strip())
    return m.group(1).lower() if m else None


# ─── Markdown parsing → blocks ────────────────────────────────────────────────

_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_HR = re.compile(r"^\s{0,3}([-*_])(\s*\1){2,}\s*$")
_UL = re.compile(r"^(\s*)[-*+]\s+(.*)$")
_OL = re.compile(r"^(\s*)(\d+)[.)]\s+(.*)$")
_TABLE_SEP = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")


def split_row(line: str) -> list[str]:
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|") and not s.endswith("\\|"):
        s = s[:-1]
    cells = re.split(r"(?<!\\)\|", s)
    return [c.strip().replace("\\|", "|") for c in cells]


def parse(md: str) -> list[tuple]:
    lines = md.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    blocks: list[tuple] = []
    para: list[str] = []
    i = 0

    def flush() -> None:
        if para:
            blocks.append(("p", para.copy()))
            para.clear()

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            flush()
            i += 1
            continue

        if stripped.startswith("```"):
            flush()
            code = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code.append(lines[i])
                i += 1
            blocks.append(("code", "\n".join(code)))
            i += 1
            continue

        m = _HEADING.match(stripped)
        if m:
            flush()
            blocks.append(("h", len(m.group(1)), m.group(2)))
            i += 1
            continue

        if _HR.match(line):
            flush()
            blocks.append(("hr",))
            i += 1
            continue

        if stripped.startswith("|") and i + 1 < len(lines) and _TABLE_SEP.match(lines[i + 1]):
            flush()
            header = split_row(stripped)
            rows = []
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                row = split_row(lines[i])
                row += [""] * (len(header) - len(row))
                rows.append(row[: len(header)])
                i += 1
            blocks.append(("table", header, rows))
            continue

        if stripped.startswith(">"):
            flush()
            quote = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote.append(re.sub(r"^\s*>\s?", "", lines[i]))
                i += 1
            blocks.append(("quote", quote))
            continue

        mu, mo = _UL.match(line), _OL.match(line)
        if mu or mo:
            flush()
            items: list[list] = []  # [level, marker, text]
            while i < len(lines):
                mu, mo = _UL.match(lines[i]), _OL.match(lines[i])
                if mu:
                    items.append([len(mu.group(1).expandtabs(4)) // 2, "•", mu.group(2)])
                elif mo:
                    items.append([len(mo.group(1).expandtabs(4)) // 2, mo.group(2) + ".", mo.group(3)])
                elif lines[i].strip() and lines[i].startswith((" ", "\t")) and items:
                    items[-1][2] += "\n" + lines[i].strip()  # continuation line
                else:
                    break
                i += 1
            blocks.append(("list", items))
            continue

        para.append(stripped)
        i += 1

    flush()
    return blocks


# ─── Inline markup ────────────────────────────────────────────────────────────

_INLINE_TOKEN = re.compile(
    r"(`[^`]+`"                        # code
    r"|\*\*.+?\*\*"                    # bold
    r"|(?<![\w*])\*(?![\s*]).+?(?<![\s*])\*(?![\w*])"  # italic
    r"|\[[^\]]+\]\([^)\s]+\))"         # link
)


def inline_runs(text: str, bold: bool = False, italic: bool = False) -> list[tuple]:
    """Split inline markdown into runs: (text, bold, italic, code, href)."""
    runs: list[tuple] = []
    pos = 0
    for m in _INLINE_TOKEN.finditer(text):
        if m.start() > pos:
            runs.append((text[pos : m.start()], bold, italic, False, None))
        tok = m.group(0)
        if tok.startswith("`"):
            runs.append((tok[1:-1], bold, italic, True, None))
        elif tok.startswith("**"):
            runs.extend(inline_runs(tok[2:-2], True, italic))
        elif tok.startswith("*"):
            runs.extend(inline_runs(tok[1:-1], bold, True))
        else:
            lm = re.match(r"\[([^\]]+)\]\(([^)\s]+)\)", tok)
            runs.append((lm.group(1), bold, italic, False, lm.group(2)))
        pos = m.end()
    if pos < len(text):
        runs.append((text[pos:], bold, italic, False, None))
    return runs


def plain(text: str) -> str:
    return "".join(r[0] for r in inline_runs(text))


# ─── HTML / PDF ───────────────────────────────────────────────────────────────

def badge(word: str) -> str:
    cls = LEVELS[word.lower()][0]
    return f'<span class="risk risk-{cls}">{html.escape(word)}</span>'


def inline_html(text: str) -> str:
    out = []
    for t, b, it, code, href in inline_runs(text):
        s = html.escape(t, quote=False).replace("\n", "<br>")
        if code:
            s = f"<code>{s}</code>"
        if href:
            s = f'<a href="{html.escape(href)}">{s}</a>'
        if it:
            s = f"<em>{s}</em>"
        if b:
            s = f"<strong>{s}</strong>"
        out.append(s)
    result = "".join(out)
    return _LEVEL_INLINE.sub(lambda m: m.group(1) + badge(m.group(2)), result)


def blocks_html(blocks: list[tuple]) -> str:
    out = []
    for b in blocks:
        kind = b[0]
        if kind == "h":
            out.append(f"<h{b[1]}>{inline_html(b[2])}</h{b[1]}>")
        elif kind == "p":
            out.append("<p>" + "<br>".join(inline_html(x) for x in b[1]) + "</p>")
        elif kind == "hr":
            out.append("<hr>")
        elif kind == "code":
            out.append(f"<pre>{html.escape(b[1])}</pre>")
        elif kind == "quote":
            out.append("<blockquote>" + "<br>".join(inline_html(x) for x in b[1]) + "</blockquote>")
        elif kind == "list":
            for level, marker, text in b[1]:
                out.append(
                    f'<div class="li" style="margin-left:{1.2 + 1.2 * level:.1f}em">'
                    f'<span class="mk">{html.escape(marker)}</span>{inline_html(text)}</div>'
                )
        elif kind == "table":
            header, rows = b[1], b[2]
            h = "".join(f"<th>{inline_html(c)}</th>" for c in header)
            body = []
            for row in rows:
                cells = []
                for c in row:
                    lvl = level_of(plain(c))
                    cells.append(f"<td>{badge(plain(c).strip(' *_')) if lvl else inline_html(c)}</td>")
                body.append("<tr>" + "".join(cells) + "</tr>")
            out.append(f"<table><thead><tr>{h}</tr></thead><tbody>{''.join(body)}</tbody></table>")
    return "\n".join(out)


def css_string(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ") + '"'


def build_html(blocks: list[tuple], title: str) -> str:
    footer = title if len(title) <= 90 else title[:87] + "…"
    risk_css = "\n".join(
        f".risk-{cls} {{ background:#{bg}; color:#{fg}; }}" for cls, bg, fg in LEVELS.values()
    )
    return f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><title>{html.escape(title)}</title>
<style>
@page {{
  size: A4; margin: 16mm 15mm 18mm 15mm;
  @bottom-left {{ content: {css_string(footer)}; font: 8pt Arial, sans-serif; color: #666; }}
  @bottom-right {{ content: "Стр. " counter(page) " из " counter(pages); font: 8pt Arial, sans-serif; color: #666; }}
}}
* {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; box-sizing: border-box; }}
body {{ font-family: "PT Sans", "Segoe UI", "Helvetica Neue", Arial, "Noto Sans", "DejaVu Sans", sans-serif;
  font-size: 10.5pt; line-height: 1.4; color: #111; margin: 0; }}
h1 {{ font-size: 16pt; margin: 0 0 8pt; }}
h2 {{ font-size: 13pt; margin: 14pt 0 6pt; padding-bottom: 2pt; border-bottom: 1pt solid #999; break-after: avoid; }}
h3, h4, h5, h6 {{ font-size: 11pt; margin: 10pt 0 4pt; break-after: avoid; }}
p {{ margin: 0 0 6pt; }}
.li {{ text-indent: -1.2em; margin: 0 0 3pt; }}
.li .mk {{ display: inline-block; width: 1.2em; text-indent: 0; }}
table {{ border-collapse: collapse; width: 100%; margin: 4pt 0 10pt; font-size: 8.8pt; line-height: 1.3; }}
thead {{ display: table-header-group; }}
tr {{ break-inside: avoid; }}
th, td {{ border: 0.6pt solid #777; padding: 3pt 4pt; vertical-align: top; text-align: left; }}
th {{ background: #e6e6e6; font-weight: 700; }}
blockquote {{ margin: 0 0 6pt; padding: 2pt 0 2pt 8pt; border-left: 2.5pt solid #999; color: #333; }}
code, pre {{ font-family: "PT Mono", Menlo, Consolas, "DejaVu Sans Mono", monospace; font-size: 9pt; }}
pre {{ white-space: pre-wrap; background: #f4f4f4; padding: 6pt; }}
hr {{ border: 0; border-top: 0.8pt solid #999; margin: 10pt 0; }}
a {{ color: #0b4f9c; word-break: break-all; }}
.risk {{ display: inline-block; padding: 0.5pt 5pt; border: 0.8pt solid #000; border-radius: 3pt;
  font-weight: 700; white-space: nowrap; }}
{risk_css}
</style></head>
<body>
{blocks_html(blocks)}
</body></html>
"""


def find_chrome() -> str | None:
    env = os.environ.get("CHROME_PATH")
    if env and Path(env).exists():
        return env
    candidates = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    for c in candidates:
        if Path(c).exists():
            return c
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
                 "microsoft-edge", "msedge", "brave-browser", "chrome"):
        p = shutil.which(name)
        if p:
            return p
    return None


def pdf_weasyprint(html_text: str, out: Path, html_path: Path) -> str | None:
    try:
        import weasyprint  # type: ignore
        weasyprint.HTML(string=html_text, base_url=str(html_path.parent)).write_pdf(str(out))
        return "weasyprint"
    except ImportError:
        pass
    cli = shutil.which("weasyprint")
    if cli:
        r = subprocess.run([cli, str(html_path), str(out)], capture_output=True, text=True, timeout=180)
        if r.returncode == 0 and out.exists():
            return "weasyprint (cli)"
        raise RuntimeError(r.stderr.strip() or "weasyprint failed")
    return None


def pdf_chrome(out: Path, html_path: Path) -> str | None:
    chrome = find_chrome()
    if not chrome:
        return None
    note = ""
    try:
        v = subprocess.run([chrome, "--version"], capture_output=True, text=True, timeout=20).stdout
        m = re.search(r"(\d+)\.", v)
        if m and int(m.group(1)) < 131:
            note = f" — WARNING: Chrome {m.group(1)} < 131, page numbers will be missing"
    except Exception:
        pass
    with tempfile.TemporaryDirectory() as profile:
        cmd = [
            chrome, "--headless", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
            "--disable-extensions", f"--user-data-dir={profile}",
            "--no-pdf-header-footer", "--print-to-pdf-no-header",
            f"--print-to-pdf={out}", html_path.resolve().as_uri(),
        ]
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            cmd.insert(1, "--no-sandbox")
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if not out.exists() or out.stat().st_size == 0:
        raise RuntimeError((r.stderr or r.stdout).strip()[-800:] or "chrome produced no PDF")
    return f"chrome ({Path(chrome).name}){note}"


def check_cyrillic(pdf: Path) -> str:
    tool = shutil.which("pdftotext")
    if not tool:
        return "not checked (no pdftotext) — open the PDF and look at it"
    r = subprocess.run([tool, "-l", "2", str(pdf), "-"], capture_output=True, text=True, timeout=60)
    text = r.stdout
    if re.search(r"[А-Яа-яЁё]{3,}", text):
        return "ok (Cyrillic text extracted)"
    return "FAILED — no Cyrillic text extracted; fonts may be missing, inspect the PDF"


# ─── DOCX (no dependencies) ───────────────────────────────────────────────────

_INVALID_XML = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def x(s: str) -> str:
    return xml_escape(_INVALID_XML.sub("", s))


def run_xml(text: str, bold=False, italic=False, code=False, color: str | None = None, size: int | None = None) -> str:
    rpr = []
    if code:
        rpr.append('<w:rFonts w:ascii="Courier New" w:hAnsi="Courier New" w:cs="Courier New"/>')
    if bold:
        rpr.append("<w:b/><w:bCs/>")
    if italic:
        rpr.append("<w:i/><w:iCs/>")
    if color:
        rpr.append(f'<w:color w:val="{color}"/>')
    if size:
        rpr.append(f'<w:sz w:val="{size}"/><w:szCs w:val="{size}"/>')
    rpr_xml = f"<w:rPr>{''.join(rpr)}</w:rPr>" if rpr else ""
    parts = text.split("\n")
    body = '<w:br/>'.join(f'<w:t xml:space="preserve">{x(p)}</w:t>' for p in parts)
    return f"<w:r>{rpr_xml}{body}</w:r>"


def runs_xml(text: str, force_bold=False, size: int | None = None) -> str:
    out = []
    for t, b, it, code, href in inline_runs(text):
        if href and href != t:
            t = f"{t} ({href})"
        out.append(run_xml(t, b or force_bold, it, code, size=size))
    return "".join(out)


def para_xml(inner: str, style: str | None = None, ind_left: int | None = None, hanging: int | None = None,
             keep_next=False, spacing_after: int | None = None) -> str:
    ppr = []
    if style:
        ppr.append(f'<w:pStyle w:val="{style}"/>')
    if keep_next:
        ppr.append("<w:keepNext/>")
    if spacing_after is not None:
        ppr.append(f'<w:spacing w:after="{spacing_after}"/>')
    if ind_left is not None:
        h = f' w:hanging="{hanging}"' if hanging else ""
        ppr.append(f'<w:ind w:left="{ind_left}"{h}/>')
    ppr_xml = f"<w:pPr>{''.join(ppr)}</w:pPr>" if ppr else ""
    return f"<w:p>{ppr_xml}{inner}</w:p>"


def table_xml(header: list[str], rows: list[list[str]]) -> str:
    border = '<w:{0} w:val="single" w:sz="4" w:space="0" w:color="808080"/>'
    borders = "".join(border.format(s) for s in ("top", "left", "bottom", "right", "insideH", "insideV"))
    out = [
        "<w:tbl><w:tblPr>"
        '<w:tblW w:w="5000" w:type="pct"/>'
        f"<w:tblBorders>{borders}</w:tblBorders>"
        '<w:tblCellMar><w:left w:w="70" w:type="dxa"/><w:right w:w="70" w:type="dxa"/></w:tblCellMar>'
        "</w:tblPr><w:tblGrid>" + '<w:gridCol/>' * len(header) + "</w:tblGrid>"
    ]

    def cell(content: str, fill: str | None) -> str:
        shd = f'<w:shd w:val="clear" w:color="auto" w:fill="{fill}"/>' if fill else ""
        return f"<w:tc><w:tcPr>{shd}</w:tcPr>{content}</w:tc>"

    def cell_paras(text: str, force_bold=False) -> str:
        return para_xml(runs_xml(text, force_bold, size=20), spacing_after=0)

    out.append('<w:tr><w:trPr><w:tblHeader/><w:cantSplit/></w:trPr>')
    out.extend(cell(cell_paras(h, True), "E6E6E6") for h in header)
    out.append("</w:tr>")
    for row in rows:
        out.append("<w:tr><w:trPr><w:cantSplit/></w:trPr>")
        for c in row:
            lvl = level_of(plain(c))
            if lvl:
                _, bg, fg = LEVELS[lvl]
                word = plain(c).strip(" *_")
                out.append(cell(para_xml(run_xml(word, bold=True, color=fg, size=20), spacing_after=0), bg))
            else:
                out.append(cell(cell_paras(c), None))
        out.append("</w:tr>")
    out.append("</w:tbl>")
    return "".join(out)


def body_xml(blocks: list[tuple]) -> str:
    out = []
    for b in blocks:
        kind = b[0]
        if kind == "h":
            out.append(para_xml(runs_xml(b[2]), style=f"Heading{min(b[1], 3)}", keep_next=True))
        elif kind == "p":
            out.append(para_xml(runs_xml("\n".join(b[1]))))
        elif kind == "quote":
            out.append(para_xml(runs_xml("\n".join(b[1])), ind_left=567))
        elif kind == "code":
            out.append(para_xml(run_xml(b[1], code=True)))
        elif kind == "hr":
            out.append('<w:p><w:pPr><w:pBdr><w:bottom w:val="single" w:sz="6" w:space="1" w:color="999999"/>'
                       "</w:pBdr></w:pPr></w:p>")
        elif kind == "list":
            for level, marker, text in b[1]:
                inner = run_xml(marker + "\t") + runs_xml(text)
                out.append(para_xml(inner, ind_left=360 + 360 * (level + 1), hanging=360, spacing_after=60))
        elif kind == "table":
            out.append(table_xml(b[1], b[2]))
            out.append(para_xml("", spacing_after=0))
    return "".join(out)


W_NS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" ' \
       'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'


def write_docx(blocks: list[tuple], out: Path, title: str) -> None:
    document = (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document {W_NS}><w:body>'
        + body_xml(blocks)
        + '<w:sectPr><w:footerReference w:type="default" r:id="rIdFooter"/>'
        '<w:pgSz w:w="11906" w:h="16838"/>'
        '<w:pgMar w:top="1134" w:right="850" w:bottom="1134" w:left="1418" w:header="567" w:footer="567" w:gutter="0"/>'
        "</w:sectPr></w:body></w:document>"
    )
    footer = (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:ftr {W_NS}>'
        '<w:p><w:pPr><w:jc w:val="right"/></w:pPr>'
        '<w:r><w:rPr><w:sz w:val="16"/></w:rPr><w:t xml:space="preserve">Стр. </w:t></w:r>'
        '<w:fldSimple w:instr=" PAGE "><w:r><w:rPr><w:sz w:val="16"/></w:rPr><w:t>1</w:t></w:r></w:fldSimple>'
        '<w:r><w:rPr><w:sz w:val="16"/></w:rPr><w:t xml:space="preserve"> из </w:t></w:r>'
        '<w:fldSimple w:instr=" NUMPAGES "><w:r><w:rPr><w:sz w:val="16"/></w:rPr><w:t>1</w:t></w:r></w:fldSimple>'
        "</w:p></w:ftr>"
    )

    def heading_style(n: int, size: int) -> str:
        return (
            f'<w:style w:type="paragraph" w:styleId="Heading{n}"><w:name w:val="heading {n}"/>'
            '<w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/>'
            f'<w:pPr><w:keepNext/><w:spacing w:before="240" w:after="120"/><w:outlineLvl w:val="{n - 1}"/></w:pPr>'
            f'<w:rPr><w:b/><w:bCs/><w:sz w:val="{size}"/><w:szCs w:val="{size}"/></w:rPr></w:style>'
        )

    styles = (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:styles {W_NS}>'
        "<w:docDefaults><w:rPrDefault><w:rPr>"
        '<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:cs="Times New Roman" w:eastAsia="Times New Roman"/>'
        '<w:sz w:val="24"/><w:szCs w:val="24"/><w:lang w:val="ru-RU"/>'
        "</w:rPr></w:rPrDefault><w:pPrDefault><w:pPr>"
        '<w:spacing w:after="120" w:line="264" w:lineRule="auto"/>'
        "</w:pPr></w:pPrDefault></w:docDefaults>"
        '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/></w:style>'
        + heading_style(1, 32) + heading_style(2, 28) + heading_style(3, 24)
        + "</w:styles>"
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
        '<Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>'
        '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
        "</Types>"
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
        "</Relationships>"
    )
    doc_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rIdStyles" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
        '<Relationship Id="rIdFooter" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" Target="footer1.xml"/>'
        "</Relationships>"
    )
    core = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        f"<dc:title>{x(title)}</dc:title><dc:language>ru-RU</dc:language>"
        f'<dcterms:created xsi:type="dcterms:W3CDTF">{date.today().isoformat()}T00:00:00Z</dcterms:created>'
        "</cp:coreProperties>"
    )
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", rels)
        z.writestr("docProps/core.xml", core)
        z.writestr("word/document.xml", document)
        z.writestr("word/styles.xml", styles)
        z.writestr("word/footer1.xml", footer)
        z.writestr("word/_rels/document.xml.rels", doc_rels)


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description="Render a Markdown contract-review report to PDF / DOCX.")
    ap.add_argument("input", help="Markdown file (UTF-8)")
    ap.add_argument("--pdf", help="output PDF path")
    ap.add_argument("--docx", help="output DOCX path")
    ap.add_argument("--html", help="also keep the intermediate HTML at this path")
    ap.add_argument("--title", help="document title (default: first heading)")
    ap.add_argument("--engine", choices=["auto", "weasyprint", "chrome"], default="auto")
    args = ap.parse_args()

    if not (args.pdf or args.docx or args.html):
        ap.error("give at least one of --pdf, --docx, --html")
    src = Path(args.input)
    if not src.is_file():
        print(f"ERROR: input not found: {src}", file=sys.stderr)
        return 1
    blocks = parse(src.read_text(encoding="utf-8-sig"))
    title = args.title or next((plain(b[2]) for b in blocks if b[0] == "h"), src.stem)
    status = 0

    if args.docx:
        out = Path(args.docx)
        out.parent.mkdir(parents=True, exist_ok=True)
        write_docx(blocks, out, title)
        print(f"DOCX: {out.resolve()}")

    if args.pdf or args.html:
        html_text = build_html(blocks, title)
        if args.html:
            Path(args.html).parent.mkdir(parents=True, exist_ok=True)
            Path(args.html).write_text(html_text, encoding="utf-8")
            print(f"HTML: {Path(args.html).resolve()}")

    if args.pdf:
        out = Path(args.pdf)
        out.parent.mkdir(parents=True, exist_ok=True)
        if out.exists():
            out.unlink()
        engine, errors = None, []
        with tempfile.TemporaryDirectory() as tmp:
            html_path = Path(tmp) / "report.html"
            html_path.write_text(html_text, encoding="utf-8")
            order = ["weasyprint", "chrome"] if args.engine == "auto" else [args.engine]
            for name in order:
                try:
                    engine = (pdf_weasyprint(html_text, out, html_path) if name == "weasyprint"
                              else pdf_chrome(out, html_path))
                except Exception as e:  # engine present but failed — try the next one
                    errors.append(f"{name}: {e}")
                    engine = None
                if engine:
                    break
        if engine:
            print(f"PDF: {out.resolve()}  [engine: {engine}]")
            print(f"Cyrillic check: {check_cyrillic(out)}")
        else:
            fallback = out.with_suffix(".html")
            fallback.write_text(html_text, encoding="utf-8")
            reason = "; ".join(errors) or "no engine found (install weasyprint, or Chrome/Chromium/Edge)"
            print(f"PDF NOT CREATED: {reason}", file=sys.stderr)
            print(f"HTML fallback: {fallback.resolve()}", file=sys.stderr)
            status = 2
    return status


if __name__ == "__main__":
    sys.exit(main())
