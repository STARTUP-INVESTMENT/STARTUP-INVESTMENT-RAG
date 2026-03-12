from __future__ import annotations

import json
import sys
from pathlib import Path

from core.graph import graph
from infra.market_vectorstore import load_or_build_vectorstore
from infra.pdf_export import build_combined_pdf


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit('Usage: python app.py "로보틱스 스타트업 투자 검토 요청"')

    user_query = sys.argv[1].strip()
    load_or_build_vectorstore()
    result = graph.invoke({"user_query": user_query, "evaluated_startups": []})

    outputs_dir = Path("outputs")
    outputs_dir.mkdir(parents=True, exist_ok=True)
    report_history = result.get("report_history", [])
    pdf_path = build_combined_pdf(
        output_path=outputs_dir / "investment_report.pdf",
        user_query=user_query,
        summary_content=result.get("report_content", ""),
        report_history=report_history,
    )

    summary = {
        "evaluated_count": len(report_history),
        "pdf_path": str(pdf_path),
        "companies": [
            {
                "startup_name": item.get("startup_name", ""),
                "decision": item.get("decision", ""),
                "final_score": item.get("final_score", 0.0),
            }
            for item in report_history
        ],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
