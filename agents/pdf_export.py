from __future__ import annotations

from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.pdfmetrics import registerFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _register_korean_font() -> str:
    font_name = "HYGothic-Medium"
    registerFont(UnicodeCIDFont(font_name))
    return font_name


def _styles(font_name: str) -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "KoreanTitle",
            parent=base["Title"],
            fontName=font_name,
            fontSize=20,
            leading=26,
            alignment=TA_LEFT,
            spaceAfter=10,
        ),
        "heading": ParagraphStyle(
            "KoreanHeading",
            parent=base["Heading2"],
            fontName=font_name,
            fontSize=14,
            leading=18,
            spaceBefore=8,
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "KoreanBody",
            parent=base["BodyText"],
            fontName=font_name,
            fontSize=10,
            leading=15,
            spaceAfter=4,
        ),
        "mono": ParagraphStyle(
            "KoreanMono",
            parent=base["Code"],
            fontName=font_name,
            fontSize=9,
            leading=13,
            spaceAfter=3,
        ),
    }


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br/>")
    )


def build_combined_pdf(
    *,
    output_path: Path,
    user_query: str,
    report_history: list[dict[str, Any]],
) -> Path:
    font_name = _register_korean_font()
    styles = _styles(font_name)
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title="Robotics Investment Report",
    )

    story: list[Any] = []
    story.append(Paragraph("로보틱스 스타트업 투자 평가 보고서", styles["title"]))
    story.append(Paragraph(f"질의: {_escape(user_query)}", styles["body"]))
    story.append(Spacer(1, 8))
    story.append(Paragraph("Summary", styles["heading"]))

    table_data = [["스타트업", "판단", "최종 점수", "핵심 사유"]]
    for item in report_history:
        table_data.append(
            [
                str(item.get("startup_name", "")),
                "투자" if str(item.get("decision", "")) == "invest" else "보류",
                str(item.get("final_score", "")),
                str(item.get("summary", "")),
            ]
        )

    summary_table = Table(table_data, colWidths=[35 * mm, 18 * mm, 22 * mm, 95 * mm], repeatRows=1)
    summary_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), font_name),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("LEADING", (0, 0), (-1, -1), 12),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E5E7EB")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#9CA3AF")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9FAFB")]),
            ]
        )
    )
    story.append(summary_table)
    story.append(PageBreak())

    for index, item in enumerate(report_history):
        if index > 0:
            story.append(PageBreak())
        story.append(Paragraph(f"{index + 1}. {str(item.get('startup_name', ''))}", styles["heading"]))
        report_content = str(item.get("report_content", ""))
        for raw_line in report_content.splitlines():
            line = raw_line.strip()
            if not line:
                story.append(Spacer(1, 4))
                continue
            if line.startswith("# "):
                continue
            if line.startswith("## "):
                story.append(Paragraph(_escape(line[3:]), styles["heading"]))
                continue
            if line.startswith("|"):
                story.append(Paragraph(_escape(line), styles["mono"]))
                continue
            story.append(Paragraph(_escape(line), styles["body"]))

    doc.build(story)
    return output_path
