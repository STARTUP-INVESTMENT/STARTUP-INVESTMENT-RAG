from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any


PDF_OPTIONS = (
    '{"format":"A4","printBackground":true,'
    '"margin":{"top":"16mm","right":"16mm","bottom":"16mm","left":"16mm"}}'
)
NOTION_LIKE_CSS = """
body {
  font-family: "Pretendard", "Apple SD Gothic Neo", "Malgun Gothic", sans-serif;
  color: #191919;
  line-height: 1.7;
  max-width: 860px;
  margin: 0 auto;
  padding: 28px 20px 40px;
  font-size: 14px;
}
h1, h2, h3, h4 { color: #111827; margin-top: 1.4em; margin-bottom: 0.5em; font-weight: 700; }
h1 { font-size: 2rem; border-bottom: 1px solid #e5e7eb; padding-bottom: 0.3em; letter-spacing: -0.02em; }
h2 { font-size: 1.4rem; border-left: 4px solid #dbeafe; padding-left: 0.6rem; }
h3 { font-size: 1.1rem; }
p, li { color: #1f2937; }
ul { padding-left: 1.3rem; }
hr { border: 0; border-top: 1px solid #e5e7eb; margin: 1.6rem 0; }
table {
  width: 100%;
  border-collapse: collapse;
  margin: 1rem 0 1.4rem;
  font-size: 13px;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.06);
}
th, td {
  border: 1px solid #e5e7eb;
  padding: 8px 10px;
  vertical-align: top;
}
th { background: #f8fafc; font-weight: 600; }
tr:nth-child(even) td { background: #fcfcfd; }
code { background: #f3f4f6; padding: 0.15rem 0.35rem; border-radius: 4px; }
blockquote {
  border-left: 3px solid #d1d5db;
  margin: 1rem 0;
  padding-left: 1rem;
  color: #4b5563;
}
.page-break { page-break-before: always; }
.cover-kicker {
  color: #2563eb;
  font-size: 0.92rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}
"""

MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def _strip_markdown_inline(text: str) -> str:
    text = MARKDOWN_LINK_RE.sub(r"\1 (\2)", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    return text.strip()


def _build_reportlab_pdf(output_path: Path, markdown: str) -> Path:
    from reportlab.lib.colors import HexColor
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title="Robotics Startup Investment Report",
    )

    styles = getSampleStyleSheet()
    body = ParagraphStyle(
        "BodyKorean",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=10.5,
        leading=16,
        textColor=HexColor("#1f2937"),
        spaceAfter=6,
    )
    heading1 = ParagraphStyle(
        "Heading1Korean",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=24,
        textColor=HexColor("#111827"),
        spaceBefore=12,
        spaceAfter=10,
    )
    heading2 = ParagraphStyle(
        "Heading2Korean",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=20,
        textColor=HexColor("#1f2937"),
        spaceBefore=10,
        spaceAfter=8,
    )
    heading3 = ParagraphStyle(
        "Heading3Korean",
        parent=styles["Heading3"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=18,
        textColor=HexColor("#1f2937"),
        spaceBefore=8,
        spaceAfter=6,
    )

    story = []
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if not line:
            story.append(Spacer(1, 4))
            continue
        if "page-break" in line:
            story.append(Spacer(1, 18))
            continue
        if line.startswith('<div class="cover-kicker">'):
            kicker = re.sub(r"<[^>]+>", "", line)
            story.append(Paragraph(_strip_markdown_inline(kicker), heading3))
            continue
        if line.startswith("# "):
            story.append(Paragraph(_strip_markdown_inline(line[2:]), heading1))
            continue
        if line.startswith("## "):
            story.append(Paragraph(_strip_markdown_inline(line[3:]), heading2))
            continue
        if line.startswith("### "):
            story.append(Paragraph(_strip_markdown_inline(line[4:]), heading3))
            continue
        if line.startswith(("- ", "* ")):
            story.append(Paragraph(f"&bull; {_strip_markdown_inline(line[2:])}", body))
            continue
        story.append(Paragraph(_strip_markdown_inline(line), body))

    doc.build(story)
    return output_path


def build_combined_markdown(*, user_query: str, summary_content: str, report_history: list[dict[str, Any]]) -> str:
    parts = [
        "# Robotics Startup Investment Report",
        "",
        '<div class="cover-kicker">Robotics Investment Report</div>',
        "",
        f"- 질의: {user_query}",
        "",
        summary_content.strip(),
    ]
    for item in report_history:
        report_content = str(item.get("report_content", "")).strip()
        if not report_content:
            continue
        parts.extend(["", '<div class="page-break"></div>', "", report_content])
    return "\n".join(parts).strip() + "\n"


def build_combined_pdf(
    *,
    output_path: Path,
    user_query: str,
    summary_content: str,
    report_history: list[dict[str, Any]],
) -> Path:
    markdown = build_combined_markdown(
        user_query=user_query,
        summary_content=summary_content,
        report_history=report_history,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    md_to_pdf_path = shutil.which("md-to-pdf")
    if not md_to_pdf_path:
        try:
            return _build_reportlab_pdf(output_path, markdown)
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "PDF 생성을 위해 `md-to-pdf` CLI 또는 `reportlab` 패키지가 필요합니다. "
                "`pip install -r requirements.txt`를 먼저 실행하세요."
            ) from exc

    with tempfile.TemporaryDirectory(prefix="investment-report-") as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        md_path = temp_dir / "investment_report.md"
        css_path = temp_dir / "notion-like.css"
        generated_pdf_path = temp_dir / "investment_report.pdf"
        md_path.write_text(markdown, encoding="utf-8")
        css_path.write_text(NOTION_LIKE_CSS, encoding="utf-8")

        subprocess.run(
            [
                md_to_pdf_path,
                str(md_path),
                "--stylesheet",
                str(css_path),
                "--pdf-options",
                PDF_OPTIONS,
            ],
            check=True,
        )
        shutil.move(str(generated_pdf_path), str(output_path))

    return output_path
