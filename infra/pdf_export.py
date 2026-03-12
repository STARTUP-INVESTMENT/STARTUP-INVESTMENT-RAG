from __future__ import annotations

from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
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
        "cover_title": ParagraphStyle(
            "KoreanCoverTitle",
            parent=base["Title"],
            fontName=font_name,
            fontSize=24,
            leading=32,
            alignment=TA_CENTER,
            spaceAfter=10,
        ),
        "cover_subtitle": ParagraphStyle(
            "KoreanCoverSubtitle",
            parent=base["Heading2"],
            fontName=font_name,
            fontSize=13,
            leading=18,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#4B5563"),
            spaceAfter=8,
        ),
        "cover_meta": ParagraphStyle(
            "KoreanCoverMeta",
            parent=base["BodyText"],
            fontName=font_name,
            fontSize=11,
            leading=16,
            alignment=TA_CENTER,
            spaceAfter=4,
        ),
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
            wordWrap="CJK",
        ),
        "mono": ParagraphStyle(
            "KoreanMono",
            parent=base["Code"],
            fontName=font_name,
            fontSize=9,
            leading=13,
            spaceAfter=3,
            wordWrap="CJK",
        ),
        "table_header": ParagraphStyle(
            "KoreanTableHeader",
            parent=base["BodyText"],
            fontName=font_name,
            fontSize=8.5,
            leading=11,
            wordWrap="CJK",
        ),
        "table_body": ParagraphStyle(
            "KoreanTableBody",
            parent=base["BodyText"],
            fontName=font_name,
            fontSize=8.5,
            leading=11,
            wordWrap="CJK",
        ),
        "small": ParagraphStyle(
            "KoreanSmall",
            parent=base["BodyText"],
            fontName=font_name,
            fontSize=8.5,
            leading=12,
            textColor=colors.HexColor("#4B5563"),
            wordWrap="CJK",
        ),
    }


def _escape(text: str) -> str:
    escaped = (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    for token in ("/", "-", "_", "?", "&amp;", "=", ":"):
        escaped = escaped.replace(token, f"{token}<wbr/>")
    return escaped.replace("\n", "<br/>")


def _paragraph(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(_escape(text), style)


def _is_markdown_table_line(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("|") and stripped.endswith("|") and stripped.count("|") >= 2


def _is_markdown_separator(line: str) -> bool:
    stripped = line.strip().strip("|").strip()
    if not stripped:
        return False
    cells = [cell.strip() for cell in stripped.split("|")]
    return all(cell and set(cell) <= {"-", ":"} for cell in cells)


def _split_markdown_row(line: str) -> list[str]:
    stripped = line.strip().strip("|")
    return [cell.strip() for cell in stripped.split("|")]


def _column_widths(rows: list[list[str]], total_width: float) -> list[float]:
    column_count = max(len(row) for row in rows)
    weights = [1] * column_count
    for row in rows:
        for index, cell in enumerate(row):
            weights[index] = max(weights[index], min(max(len(cell), 1), 30))
    weight_sum = sum(weights) or column_count
    min_width = 18 * mm
    widths = [max(min_width, total_width * weight / weight_sum) for weight in weights]
    overflow = sum(widths) - total_width
    if overflow > 0:
        shrinkable = [index for index, width in enumerate(widths) if width > min_width]
        while overflow > 0.1 and shrinkable:
            reduction = overflow / len(shrinkable)
            next_shrinkable: list[int] = []
            for index in shrinkable:
                allowed = widths[index] - min_width
                delta = min(reduction, allowed)
                widths[index] -= delta
                overflow -= delta
                if widths[index] - min_width > 0.1:
                    next_shrinkable.append(index)
            shrinkable = next_shrinkable
    return widths


def _build_markdown_table(
    lines: list[str],
    *,
    styles: dict[str, ParagraphStyle],
    total_width: float,
) -> Table | None:
    if len(lines) < 2 or not _is_markdown_separator(lines[1]):
        return None
    rows = [
        _split_markdown_row(line)
        for index, line in enumerate(lines)
        if _is_markdown_table_line(line) and (index == 0 or not _is_markdown_separator(line))
    ]
    if not rows:
        return None
    column_count = max(len(row) for row in rows)
    normalized: list[list[Paragraph]] = []
    for row_index, row in enumerate(rows):
        padded = row + [""] * (column_count - len(row))
        style = styles["table_header"] if row_index == 0 else styles["table_body"]
        normalized.append([_paragraph(cell, style) for cell in padded])
    table = Table(normalized, colWidths=_column_widths(rows, total_width), repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), styles["table_body"].fontName),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("LEADING", (0, 0), (-1, -1), 11),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E5E7EB")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#9CA3AF")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9FAFB")]),
            ]
        )
    )
    return table


def _front_matter_table(
    rows: list[tuple[str, str]],
    *,
    styles: dict[str, ParagraphStyle],
    total_width: float,
) -> Table:
    table_rows: list[list[Paragraph]] = []
    for label, value in rows:
        table_rows.append(
            [
                _paragraph(label, styles["table_header"]),
                _paragraph(value, styles["table_body"]),
            ]
        )
    table = Table(table_rows, colWidths=[32 * mm, total_width - 32 * mm])
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), styles["table_body"].fontName),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("LEADING", (0, 0), (-1, -1), 12),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F3F4F6")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def build_combined_pdf(
    *,
    output_path: Path,
    user_query: str,
    summary_content: str,
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
    evaluated_count = len(report_history)
    decision_counts = {
        "invest": sum(1 for item in report_history if str(item.get("decision", "")) == "invest"),
        "hold": sum(1 for item in report_history if str(item.get("decision", "")) != "invest"),
    }
    prepared_by = "배민, 이성민, 임세하, 정찬혁"

    story.append(Spacer(1, 85))
    story.append(Paragraph("Robotics Startup", styles["cover_subtitle"]))
    story.append(Paragraph("Investment Report", styles["cover_title"]))
    story.append(Spacer(1, 12))
    story.append(Paragraph("로보틱스 스타트업 투자 평가 보고서", styles["cover_subtitle"]))
    story.append(Spacer(1, 24))
    story.append(_paragraph(f"Prepared by: {prepared_by}", styles["cover_meta"]))
    story.append(_paragraph(f"평가 대상 기업 수: {evaluated_count}", styles["cover_meta"]))
    story.append(_paragraph(f"투자 추천 {decision_counts['invest']}개 / 보류 {decision_counts['hold']}개", styles["cover_meta"]))
    story.append(_paragraph(f"작성 질의: {user_query}", styles["cover_meta"]))
    story.append(Spacer(1, 34))
    story.append(
        _front_matter_table(
            [
                ("문서 목적", "후보 스타트업의 투자 적합도를 기술, 시장, 경쟁, 사업성 관점에서 비교 평가"),
                ("평가 방법", "7개 항목 Scorecard 기반 정성·정량 혼합 평가"),
                ("보고서 범위", "후보사 요약, 기업별 상세 분석, 점수 비교, 핵심 리스크 및 투자 제언"),
                ("유의 사항", "공개 자료 기반 초안이며 실제 투자 전 추가 실사와 검증이 필요"),
            ],
            styles=styles,
            total_width=doc.width,
        )
    )
    story.append(Spacer(1, 18))
    story.append(
        _paragraph(
            "본 보고서는 초기 검토 목적의 투자 문서로, 공개 자료와 수집 가능한 근거를 기반으로 작성되었다.",
            styles["small"],
        )
    )
    story.append(Paragraph("Summary", styles["title"]))
    story.append(_paragraph(f"질의: {user_query}", styles["body"]))
    story.append(Spacer(1, 8))
    for raw_line in [*summary_content.splitlines(), ""]:
        line = raw_line.strip()
        if not line or line.startswith("# "):
            if not line:
                story.append(Spacer(1, 4))
            continue
        if line.startswith("## "):
            story.append(_paragraph(line[3:], styles["heading"]))
            continue
        story.append(_paragraph(line, styles["body"]))
    story.append(Spacer(1, 12))

    for index, item in enumerate(report_history):
        if index > 0:
            story.append(Spacer(1, 14))
        story.append(_paragraph(f"{index + 1}. {str(item.get('startup_name', ''))}", styles["heading"]))
        report_content = str(item.get("report_content", ""))
        table_buffer: list[str] = []
        for raw_line in [*report_content.splitlines(), ""]:
            line = raw_line.strip()
            if _is_markdown_table_line(line):
                table_buffer.append(line)
                continue
            if table_buffer:
                table = _build_markdown_table(table_buffer, styles=styles, total_width=doc.width)
                if table is not None:
                    story.append(table)
                    story.append(Spacer(1, 6))
                else:
                    for buffered in table_buffer:
                        story.append(_paragraph(buffered, styles["mono"]))
                table_buffer = []
            if not line:
                story.append(Spacer(1, 4))
                continue
            if line.startswith("# "):
                continue
            if line.startswith("## "):
                story.append(_paragraph(line[3:], styles["heading"]))
                continue
            story.append(_paragraph(line, styles["body"]))

    doc.build(story)
    return output_path
