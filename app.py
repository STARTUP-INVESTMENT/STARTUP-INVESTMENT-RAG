from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from core.graph import graph
from infra.pdf_export import build_combined_pdf


def main() -> None:
    start = time.time()
    print("Starting...")

    if len(sys.argv) < 2:
        raise SystemExit('Usage: python app.py "로보틱스 스타트업 투자 검토 요청"')

    user_query = sys.argv[1].strip()
    result = graph.invoke({"user_query": user_query, "evaluated_startups": []})

    outputs_dir = Path("outputs")
    outputs_dir.mkdir(parents=True, exist_ok=True)
    report_history = result.get("report_history", [])
    company_summaries: list[dict[str, object]] = []
    for item in report_history:
        startup_name = str(item.get("startup_name", "report"))
        slug = startup_name.replace("/", "-").replace(" ", "_") 
        report_path = outputs_dir / f"{slug}.md"
        report_path.write_text(str(item.get("report_content", "")), encoding="utf-8")
        company_summaries.append(
            {
                "startup_name": startup_name,
                "decision": item.get("decision", ""),
                "final_score": item.get("final_score", 0.0),
                "report_path": str(report_path),
            }
        )
    summary_content = result.get("report_content", "")
    summary_path = outputs_dir / "summary.md"
    summary_path.write_text(result.get("report_content", ""), encoding="utf-8")
    pdf_path = build_combined_pdf(
        output_path=outputs_dir / "investment_report.pdf",
        user_query=user_query,
        summary_content=summary_content,
        report_history=report_history,
    )

    summary = {
        "evaluated_count": len(company_summaries),
        "summary_path": str(summary_path),
        "pdf_path": str(pdf_path),
        "companies": company_summaries,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    end = time.time()
    print(f"Total execution time: {end - start:.2f} seconds")

if __name__ == "__main__":
    main()
