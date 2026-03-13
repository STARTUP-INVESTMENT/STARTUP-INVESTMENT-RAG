# Robotics Startup Investment Evaluation Agent

본 프로젝트는 **로보틱스(Robotics)** 스타트업에 대한 투자 가능성을 자동으로 평가하는 에이전트를 설계하고 구현한 실습 프로젝트입니다.

---

## Overview

- **Objective** : 로보틱스 스타트업의 기술력, 시장성, 경쟁 환경, 팀, 리스크를 기준으로 투자 적합성 분석 및 `투자 추천 / 관심 보류` 판단 자동 생성
- **Method** : AI Agent + Agentic RAG
- **Tools** : FAISS Vector Search, Tavily Web Search

---

## Features

- **스타트업 후보 탐색** : 사용자 쿼리 기반으로 Algolia API를 통해 Y Combinator 스타트업 후보군 수집
- **Agentic RAG 기반 근거 수집** : 에이전트별 Tavily 웹 검색 + FAISS 벡터 스토어(로보틱스 산업 기술 및 시장 동향 보고서)를 병행해 평가 근거 수집
- **스코어카드 기반 평가** : 로보틱스 전문 VC의 투자 평가 기준이 반영된 팀·기술·시장·경쟁·ROI·안전·수익모델 가중합산을 통한 평가 후 최종 투자 적합성 판단
- **종합 투자 보고서 생성** : 스코어카드 평가 결과를 바탕으로 투자 의견, 핵심 근거(기술력, 시장성) 등 구조화된 투자 보고서 생성

---

## Tech Stack

| Category     | Details                                        |
|--------------|------------------------------------------------|
| Framework    | LangGraph, LangChain, Python                   |
| LLM          | GPT-4.1-mini via OpenAI API                    |
| Retrieval    | FAISS, Tavily Search API, Algolia Search API   |
| Embedding    | `intfloat/multilingual-e5-large-instruct`      |

---

## Agents

| Agent | 역할 |
|-------|------|
| **스타트업 탐색 에이전트** | YC 스타트업 후보 탐색, LLM 관련성 필터로 평가 대상 선정 |
| **기술력 평가 에이전트** | Tavily + FAISS → 기술력(TRL 1~9), 팀·창업자, 안전인증·규제 평가 |
| **시장성 평가 에이전트** | Tavily + FAISS → 시장 기회(TAM/SAM), 고객 ROI·트랙션, 수익모델 평가 |
| **경쟁사 비교 에이전트** | Tavily → 경쟁사 매핑, 기술 해자·차별화 포인트 분석 |
| **투자 판단 에이전트** | 7개 카테고리 스코어카드 가중합산 → `invest / hold` 최종 판단 |
| **보고서 생성 에이전트** | 종합 투자 보고서 생성 |

---

## Architecture
[이미지 첨부]

## Directory Structure

```text
.
├── agents/                    # 평가 에이전트 모듈
│   ├── startup_search_agent.py
│   ├── tech_evaluation_agent.py
│   ├── market_evaluation_agent.py
│   ├── competitor_analysis_agent.py
│   ├── investment_decision_agent.py
│   └── report_writer_agent.py
├── core/                      # 핵심 공유 모듈
│   ├── graph.py               # LangGraph 오케스트레이션
│   ├── state.py               # InvestmentState 정의
│   ├── agent_utils.py         # LLM 호출·JSON 파싱 유틸
│   └── prompt_loader.py       # 프롬프트 파일 로더
├── infra/                     # 인프라 레이어
│   ├── embeddings.py          # E5Instruct 임베딩 래퍼
│   ├── market_vectorstore.py  # FAISS 빌드·로드·검색
│   ├── research_utils.py      # Tavily 검색·캐시·포맷 유틸
│   └── pdf_export.py          # PDF 보고서 생성
├── data/                      # 로보틱스 산업 리포트 PDF (RAG 소스)
├── prompts/                   # 프롬프트 템플릿
├── outputs/                   # 평가 결과 (MD, PDF)
├── app.py                     # 실행 진입점
├── requirements.txt
└── README.md
```

## Contributors
[수정 필요]
- **배민** : LangGraph 파이프라인 설계, Startup Search Agent (YC·혁신의숲 크롤링, LLM 필터링)
- **이성민** : FAISS 벡터 스토어 구축, 임베딩 모듈(multilingual-e5-large-instruct), RAG 파이프라인 연동
- **임세하** : Market Evaluation Agent (시장·ROI·수익모델), Competitor Analysis Agent, 스코어카드 설계
- **정찬혁** : Tech Evaluation Agent (TRL·팀·안전규제), Investment Decision Agent, Report Writer (MD·PDF)
