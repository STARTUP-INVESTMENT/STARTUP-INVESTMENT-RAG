# AI Startup Investment Evaluation Agent
본 프로젝트는 **로보틱스(robotics) 스타트업**에 대한 투자 가능성을 자동으로 평가하는 에이전트를 설계하고 구현한 실습 프로젝트입니다.

## Overview

- Objective : 로보틱스 스타트업의 기술력, 시장성, 경쟁 구도, 리스크를 기준으로 투자 적합성 분석
- Method : AI Agent + Agentic RAG (웹 리서치 + PDF 기반 벡터 검색)
- Tools : Y Combinator Algolia API, Tavily Search API, FAISS Vector Store

## Features

- PDF 자료 기반 정보 추출 (예: 산업 리포트/백서/기사 PDF)
- 투자 기준별 판단 분류 (팀/기술/시장/경쟁/ROI/규제/수익모델)
- 종합 투자 요약 출력 (현재 기준: `투자 추천` / `보류`)
- 기업별 보고서 Markdown 생성 + 통합 PDF 리포트 자동 생성

## Tech Stack

| Category   | Details |
|------------|---------|
| Framework  | LangGraph, LangChain, Python |
| LLM        | gpt-4.1-mini via OpenAI API |
| Retrieval  | FAISS (PDF RAG), Tavily Web Retrieval |
| Embedding  | intfloat/multilingual-e5-large-instruct |

## Agents

- `startup_search_agent`: YC 기반 후보 스타트업 탐색 및 관련성 필터링
- `tech_evaluation_agent`: 기술력/TRL/팀/안전·규제 평가
- `market_evaluation_agent`: 시장성/ROI·트랙션/수익모델 평가
- `competitor_analysis_agent`: 경쟁사 및 차별화 포지션 분석
- `investment_decision_agent`: 가중치 스코어카드 기반 최종 투자 판단
- `report_writer_agent`: 최종 투자 리포트(한국어) 작성

## Architecture

- 오케스트레이션: `startup_search -> (tech_evaluation, market_evaluation, competitor_analysis) -> investment_decision -> collect_company_result`
- 반복 평가: 후보 리스트를 순회하며 기업별 평가를 반복 수행
- 최종 단계: `report_writer`에서 통합 요약 생성 후 `outputs/investment_report.pdf`로 내보내기

(그래프 이미지는 추후 추가)

## Directory Structure

```text
.
├── data/                  # 로보틱스 PDF 문서(RAG 원문)
├── agents/                # 평가 기준별 Agent 모듈
├── core/                  # 상태 정의, 그래프 구성, 공통 유틸
├── infra/                 # 벡터스토어/리서치/PDF export 인프라
├── prompts/               # 프롬프트 템플릿
├── outputs/               # 평가 결과 저장
├── app.py                 # 실행 스크립트
├── requirements.txt
└── README.md
```

## Contributors

- 배민
- 이성민
- 임세하
- 정찬혁