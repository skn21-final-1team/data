# 🗃️ data

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.131-009688?logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-pgvector-4169E1?logo=postgresql&logoColor=white)
![RunPod](https://img.shields.io/badge/RunPod-Serverless-7B2FBE)
![Playwright](https://img.shields.io/badge/Playwright-Chromium-2EAD33?logo=playwright&logoColor=white)
![Ruff](https://img.shields.io/badge/Ruff-lint-D7FF64?logo=ruff&logoColor=black)

> 웹 페이지를 크롤링하고 vLLM으로 정제·요약한 뒤 청킹·임베딩하여 벡터 DB에 적재하는 ETL 파이프라인 서버.

---

## 개요

|        단계        | 처리 내용                                                 | 기술                                          |
| :-----------------: | --------------------------------------------------------- | --------------------------------------------- |
|  **Extract**  | 하이브리드 크롤링, robots.txt 검증, 콘텐츠 유효성 검사    | Trafilatura, Playwright                       |
| **Transform** | LLM 정제·요약 → HierarchicalPrepend 청킹 → 벡터 임베딩 | RunPod Serverless (Llama-3.1-8B, BAAI/bge-m3) |
|   **Load**   | 벡터 저장 및 HNSW 인덱싱                                  | PostgreSQL + pgvector                         |

---

## 시스템 구조

### 파이프라인 흐름

```
POST /crawl
    │
    ├─ [Extract]
    │      └─ HybridClient.scrape()
    │              ├─ Trafilatura  ← 정적 크롤링 (HTTP)
    │              └─ Playwright   ← 동적 크롤링 (JS 렌더링)
    │
    ├─ [Transform]
    │      ├─ vLLM.refine()        ← RunPod Serverless (Llama-3.1-8B)
    │      ├─ vLLM.summarize()     ← RunPod Serverless
    │      ├─ Chunker              ← HierarchicalPrependChunker
    │      └─ Embed.embed_texts()  ← RunPod Serverless (BAAI/bge-m3)
    │
    └─ [Load]
           └─ pgvector             ← PostgreSQL HNSW Index
```

### 디렉토리 구조

```
data/
├── api/          # FastAPI 라우터 (crawl, health)
├── chunk/        # HierarchicalPrependChunker
├── core/         # 설정, 로깅, 예외
├── crawl/        # HybridClient, 검증, 파싱, robots
├── crud/         # SQLAlchemy CRUD
├── db/           # 세션, 벡터스토어
├── embed/        # RunPod 임베딩 서비스
├── llm/          # RunPod vLLM 클라이언트
├── models/       # ORM 모델
├── schemas/      # Pydantic 스키마
├── services/     # crawl_pipeline (ETL 오케스트레이션)
├── alembic/      # DB 마이그레이션
└── main.py       # FastAPI 진입점
```

---

## 기술 스택

| 영역               | 기술                                        |
| ------------------ | ------------------------------------------- |
| 웹 프레임워크      | FastAPI + Uvicorn                           |
| 크롤링             | Trafilatura, Playwright, playwright-stealth |
| LLM                | RunPod Serverless — Llama-3.1-8B-Instruct  |
| 임베딩             | RunPod Serverless — BAAI/bge-m3            |
| 청킹               | LangChain HierarchicalPrependChunker        |
| 데이터베이스       | PostgreSQL + pgvector (HNSW)                |
| ORM / 마이그레이션 | SQLAlchemy + Alembic                        |
| 패키지 관리        | uv                                          |
| 린팅 / 포매팅      | Ruff                                        |
| 배포               | AWS EC2 + SSM + GitHub Actions              |
| 알림               | Discord Webhook                             |
| Python             | 3.12                                        |

---

## 실행 전 필수 사항

프로젝트 루트에 `.env` 파일을 생성하고 아래 항목을 설정한다.

| 변수                     | 설명                     | 예시                                     |
| ------------------------ | ------------------------ | ---------------------------------------- |
| `DATABASE_URL`         | PostgreSQL 접속 URL      | `postgresql+psycopg://user:pw@host/db` |
| `RUNPOD_API_KEY`       | RunPod 인증 키           | `rpa_xxx...`                           |
| `VLLM_BASE_URL`        | RunPod vLLM 엔드포인트   | `https://api.runpod.ai/v2/{id}`        |
| `VLLM_MODEL`           | LLM 모델명               | `meta-llama/Llama-3.1-8B-Instruct`     |
| `EMBED_BASE_URL`       | RunPod 임베딩 엔드포인트 | `https://api.runpod.ai/v2/{id}`        |
| `EMBED_MODEL`          | 임베딩 모델명            | `BAAI/bge-m3`                          |
| `BACKEND_CALLBACK_URL` | 크롤링 완료 콜백 URL     | `http://host:port/`                    |

---

## 초기 세팅

```bash
# 의존성 설치
uv sync                  # 운영 환경
uv sync --extra dev      # 개발 환경 (ruff 포함)

# Playwright 브라우저 설치 (최초 1회)
uv run playwright install chromium

# (Ubuntu/Linux) 시스템 의존성 설치 — EC2 최초 1회
sudo $(which playwright) install-deps chromium

# DB 마이그레이션
uv run alembic upgrade head
```

### 의존성 구분

| 구분           | 설치 명령               | 포함 패키지                                                      |
| -------------- | ----------------------- | ---------------------------------------------------------------- |
| **core** | `uv sync`             | FastAPI, httpx, Playwright, Trafilatura, SQLAlchemy, pgvector 등 |
| **dev**  | `uv sync --extra dev` | ruff                                                             |

---

## 서버 실행

```bash
# 로컬 개발
uvicorn main:app --reload --port 8001

# 운영 (EC2)
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 2
```

---

## Ruff 린팅 및 포매팅

```bash
# 검사
ruff check .
ruff format --check .

# 자동 수정
ruff check --fix .
ruff format .
```

---

## API 문서

### 엔드포인트 목록

| Method   | Path            | 설명                               |
| -------- | --------------- | ---------------------------------- |
| `GET`  | `/`           | 루트 상태 확인                     |
| `GET`  | `/health`     | DB 연결 상태 확인                  |
| `POST` | `/crawl`      | URL 크롤링 요청 (비동기 처리)      |
| `POST` | `/crawl/sync` | 북마크 동기화 크롤링 (비동기 처리) |

### POST `/crawl`

```json
// Request
{
  "sources": [
    { "source_id": 1, "url": "https://example.com" }
  ]
}

// Response
{ "status": "accepted", "accepted": [1], "not_found": [] }
```

### POST `/crawl/sync`

```json
// Request
{ "source_ids": [1, 2, 3], "notebook_id": 10 }

// Response
{ "status": "accepted", "accepted": [1, 2, 3], "not_found": [] }
```

### 대화형 문서

- **Swagger UI**: http://localhost:8001/docs
- **ReDoc**: http://localhost:8001/redoc

---

## 배포

`devops` 브랜치 push 시 GitHub Actions 자동 배포.

1. AWS OIDC 인증
2. AWS SSM으로 EC2에 `dev-deploy.sh` 원격 실행
3. Discord 알림 (시작 🟡 / 완료 🟢 / 실패 🔴)
