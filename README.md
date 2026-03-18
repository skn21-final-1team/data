# Data

웹 페이지를 크롤링하고, vLLM으로 정제/요약한 뒤 청킹·임베딩하여 벡터 DB에 적재하는 데이터 파이프라인 서버.

- **Extract** — Trafilatura + Playwright 하이브리드 크롤링
- **Transform** — vLLM 정제/요약 (RunPod Serverless) → HierarchicalPrepend 청킹 → 서버리스 임베딩
- **Load** — PostgreSQL + pgvector (HNSW 인덱스)

### 기술 스택

FastAPI · Uvicorn · SQLAlchemy · pgvector · Trafilatura · Playwright · RunPod Serverless (vLLM + Embedding)

## 실행 전 필수 사항

1. `.env` 파일 설정 (본인 환경에 맞게)

## 초기 세팅 (pull 이후)

```bash
# 서비스 의존성만 설치 (배포/RunPod 등 운영 환경)
uv sync

# 실험·평가 의존성 포함 설치 (로컬 개발 환경)
uv sync --extra dev

# Playwright 브라우저 설치 (최초 1회만)
uv run playwright install chromium
```

### 의존성 구분

| 구분 | 설치 명령 | 포함 패키지 |
|---|---|---|
| **core** | `uv sync` | FastAPI, httpx, Playwright, Trafilatura, SQLAlchemy, pgvector, langchain-postgres 등 |
| **dev** | `uv sync --extra dev` | ruff |

## 서버 실행

```bash
uvicorn main:app --reload --port 8001
```

## ruff 린팅 및 포맷팅 확인

```bash
ruff check .
ruff format --check .
```

## API 문서

- Swagger UI: http://localhost:8001/docs
- ReDoc: http://localhost:8001/redoc

<br><br><br>
# dev 서버 설정

## UV 설치
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## tmux 명령어
### create session
```bash
tmux new -s [name] 
```
### hide & visible tmux
```bash
ctrl + b + d #hide
tmux -a -t [name] # visible
```


## 서버실행 및 로깅
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 > fastapi.log 2>&1 &
```