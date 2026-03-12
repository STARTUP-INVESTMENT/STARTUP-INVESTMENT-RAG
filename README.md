# Robotics Investment Agent

로보틱스 스타트업 후보를 탐색하고, 기술/시장/경쟁/투자 판단을 순차적으로 수행하는 Python 기반 멀티 에이전트 프로젝트다.

## Directory Structure

```text
.
├── agents/      # 평가 기준별 Agent 모듈
├── data/        # 스타트업 PDF 문서 및 RAG 원문
├── outputs/     # 평가 결과 저장
├── prompts/     # 프롬프트 템플릿
├── app.py       # 실행 스크립트
├── README.md
└── requirements.txt
```

## Agents

- `agents/startup_search_agent.py`: YC + 혁신의숲 기반 후보 탐색
- `agents/graph.py`: LangGraph 오케스트레이션
- `agents/tech_evaluation_agent.py`: 기술 평가 에이전트
- `agents/market_evaluation_agent.py`: 시장 평가 에이전트
- `agents/competitor_analysis_agent.py`: 경쟁 분석 에이전트
- `agents/investment_decision_agent.py`: 스코어카드 및 투자 판단 에이전트
- `agents/report_writer_agent.py`: 기업별 보고서 작성 에이전트
- `agents/state.py`: LangGraph 상태 정의
- `agents/prompt_loader.py`: 프롬프트 파일 로더

## Prompts

- `prompts/startup_search_keywords.txt`
- `prompts/startup_relevance_filter.txt`
- `prompts/startup_search_state.txt`
- `prompts/tech_evaluation.txt`
- `prompts/market_evaluation.txt`
- `prompts/competitor_analysis.txt`

## Run

`.env`에 `OPENAI_API_KEY`를 넣은 뒤 실행:

```bash
source .venv/bin/activate
python app.py "휴머노이드 로보틱스 스타트업 투자 검토"
```

실행 결과:

- 검색과 평가를 수행한 뒤 JSON 요약을 stdout에 출력
- 최종 보고서를 `outputs/<startup_name>.md`에 저장
- 전체 요약 + 기업별 상세 섹션을 묶은 단일 PDF를 `outputs/investment_report.pdf`에 저장

## Data

- `data/`에는 PDF, 백서, 특허 요약 등 RAG 문서를 둔다
- 현재 구현은 웹 탐색 중심이며, 이후 `data/` 문서를 RAG 파이프라인에 연결하면 된다
