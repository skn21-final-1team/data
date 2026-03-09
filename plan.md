# Data 서버 작업 계획

> 크롤링 → vLLM 정제/요약 → 청킹 → 임베딩 → PGVector 적재

---

## 1. API 연동 (완료)

- [X] `POST /crawl` — URL 수신 → 즉시 응답 → 백그라운드 파이프라인
- [X] `GET /health` — 서버 상태 확인
- [X] 글로벌 예외 핸들러 (422 + 500)
- [X] `source.status` 컬럼 (pending → success/failed)
- [X] 비동기 파이프라인 — URL별 독립 처리
- [X] 서버리스 임베딩 (RunPod /runsync)
- [X] 서버리스 vLLM 정제/요약 (RunPod /run + polling)
- [X] 쿼리 임베딩은 backend에서 직접 처리 (data 서버 미관여)

---

## 2. 실험

### 테스트 파이프라인

```
test_crawl   → DB(summary=전처리 본문)
test_vllm    → DB(summary=요약) + output/refined.json
test_chunk   → output_analysis/chunk/{comparison.csv, total_analysis.md} + output/chunks.json
test_embed   → PGVector 적재
evaluation_ir → IR 지표 평가
```

### 실험 도구

| 도구 | 용도 | 실행 |
|---|---|---|
| `test/test_crawl.py` | 크롤링 → 전처리 → source DB 적재 | `uv run python -m test.test_crawl {notebook_id}` |
| `test/test_vllm.py` | vLLM 정제/요약 → summary 업데이트 + refined.json | `uv run python -m test.test_vllm --ids 1 2 3` |
| `test/test_chunk.py` | 청킹 전략 비교 평가 → CSV/MD 산출 + chunks.json | `uv run python -m test.test_chunk` |
| `test/test_embed.py` | 임베딩 → PGVector 적재 | `uv run python -m test.test_embed --test --clear` |
| `test/evaluation_ir.py` | IR 지표 평가 (Hit Rate, MRR, NDCG) | `uv run python -m test.evaluation_ir --mode reranker --top_k 5` |

---

### 실험 변수

#### A. 청킹 전략 (10종)

**기본 전략 (6종)**

| ID | 전략 | 설명 |
|---|---|---|
| S1 | `recursive` | RecursiveCharacterTextSplitter (베이스라인) |
| S2 | `token` | TokenTextSplitter (tiktoken cl100k_base) |
| S3 | `semantic` | SemanticChunker (임베딩 유사도 기반, size/overlap 자동) |
| S4 | `markdown_header` | MarkdownHeaderTextSplitter (H1/H2/H3 기준, size/overlap 자동) |
| S5 | `markdown` | MarkdownTextSplitter (현재 서비스) |
| S6 | `hierarchical` | MarkdownHeader → Recursive 재분할 |

**헤더 경로 Prepend 변형 (2종)**

| ID | 전략 | 설명 |
|---|---|---|
| S5-P | `markdown_prepend` | S5 + 헤더 경로 주입 (`[# A > ## B] 본문...`) |
| S6-P | `hierarchical_prepend` | S6 + 헤더 경로 주입 |

**고급 전략 (2종)**

| ID | 전략 | 설명 | 비고 |
|---|---|---|---|
| S7 | `contextual` | Contextual Retrieval (GPT-4o 맥락 요약 prepend) | OPENAI_API_KEY 필요 |
| S9 | `sentence_window` | 문장 단위 분할 + 주변 window 확장 | |

> S8 Late Chunking: 서버리스 환경에서 모델 아키텍처 직접 접근 불가 → 제외

#### B. 청킹 사이즈 / 오버랩 조합

| ID | chunk_size | chunk_overlap | 비율 |
|---|---|---|---|
| C1 | 256 | 30 | 11.7% |
| C2 | 500 | 50 | 10.0% |
| C3 | 800 | 100 | 12.5% |
| C4 | 1000 | 100 | 10.0% (현재) |
| C5 | 1000 | 200 | 20.0% |
| C6 | 1500 | 150 | 10.0% |
| C7 | 2000 | 200 | 10.0% |

#### C. 임베딩 모델 (3종)

| ID | 모델 | 차원 | 비고 |
|---|---|---|---|
| E1 | `BAAI/bge-m3` | 1024 | 현재 서비스 기본 모델 |
| E2 | `intfloat/multilingual-e5-large` | 1024 | 기존 비교 모델 |
| E3 | `OpenAI/text-embedding-3-large` | 3072 | 차원 변경 + DB 마이그레이션 필요 |

#### D. 검색 설정 (고정)

| 항목 | 값 |
|---|---|
| mode | reranker |
| 벡터검색 top_k | 20 |
| rerank 후 top_k | 5 |
| reranker 모델 | bge-reranker-v2-m3 |

#### E. 평가 지표

**IR 지표 (LLM 불필요, 비용 0)**

| 지표 | 설명 |
|---|---|
| Hit Rate@5 | 정답 chunk가 top-5 안에 존재하는 비율 |
| MRR | 첫 번째 정답 chunk의 순위 역수 평균 |
| NDCG@5 | 순위 품질 (상위 배치에 가중치) |

**청킹 품질 지표 (test_chunk 자동 산출)**

| 지표 | 설명 |
|---|---|
| paragraph | 단락 경계 보존율 |
| sentence | 문장 무결성 (경계에서 깨지지 않는 비율) |
| whitespace | 원본 공백 구조 보존율 |
| list | 리스트 항목 보존율 |
| heading | 헤더가 청크 시작부에 위치하는 비율 |
| coverage | 청크 총 길이 / 원본 길이 (1.0 최적) |
| boundary | 자연스러운 위치에서 끊기는 비율 |

---

### 실험 순서

#### Phase 1: 청킹 전략 비교 (E1 고정, C4 기본)

임베딩 모델 `BAAI/bge-m3` 고정, 10개 전략 비교:

```bash
# 1) 데이터 준비
uv run python -m test.test_crawl {notebook_id}

# 2) vLLM 정제 (서버 가용 시)
uv run python -m test.test_vllm

# 3) 전략 비교 (전체)
uv run python -m test.test_chunk

# 3-1) LLM 비용 전략 제외하고 실행
uv run python -m test.test_chunk --strategies recursive token semantic markdown_header markdown hierarchical markdown_prepend hierarchical_prepend sentence_window

# 3-2) S7 Contextual만 별도 실행 (OPENAI_API_KEY 필요)
uv run python -m test.test_chunk --strategies contextual

# 4) 상위 전략으로 임베딩 + 적재
uv run python -m test.test_chunk --strategies markdown --best markdown
uv run python -m test.test_embed --test --clear

# 5) IR 평가
uv run python -m test.evaluation_ir --mode reranker --top_k 5
```

산출물: `test/output_analysis/chunk/comparison.csv`, `total_analysis.md`

#### Phase 2: 최적 전략의 사이즈 튜닝

Phase 1 상위 2~3개 전략 → 사이즈 조합 테스트:

```bash
# 예: markdown 전략으로 사이즈 변경
uv run python -m test.test_chunk --strategies markdown --chunk_size 500 --chunk_overlap 50
uv run python -m test.test_chunk --strategies markdown --chunk_size 800 --chunk_overlap 100
uv run python -m test.test_chunk --strategies markdown --chunk_size 1500 --chunk_overlap 150
```

#### Phase 3: 임베딩 모델 비교

Phase 2 확정 전략+사이즈로 임베딩 모델 교체 비교:

```bash
# E1: BAAI/bge-m3 (기본)
uv run python -m test.test_embed --test --clear

# E2: multilingual-e5-large (.env에서 EMBED_MODEL 변경 후)
uv run python -m test.test_embed --test --clear
```

> E3 (3072차원) 테스트 시 `models/page_data.py` 차원 변경 + DB 마이그레이션 필요

#### Phase 4: 고급 전략 (선택)

| # | 전략 | 비고 |
|---|---|---|
| 4-1 | S7 Contextual Retrieval | GPT-4o 호출 비용 발생, OPENAI_API_KEY 필요 |
| 4-2 | S9 Sentence Window | window_size 튜닝 필요 |

---

## 3. MLflow 실험 기록

### 설치 및 실행

```bash
uv sync --extra dev
uv run mlflow ui --port 5000
# http://localhost:5000 접속
```

### 기록 항목

`test/evaluation_ir.py` 실행 시 `mlruns/`에 자동 기록:

| 구분 | 항목 |
|---|---|
| **params** | embed_model, chunk_strategy, chunk_size, chunk_overlap, mode, top_k |
| **metrics** | hit_rate, mrr, ndcg |
| **artifacts** | results.json, details.json |

### 사용법

1. 좌측 사이드바 → `retriever-evaluation` 실험 선택
2. 비교할 run들을 체크박스로 선택 → **Compare** 버튼
3. 차트/테이블로 params와 metrics 비교

### 예시

```
Run 1: markdown,    chunk_size=1000 → hit_rate=0.65, mrr=0.45, ndcg=0.52
Run 2: recursive,   chunk_size=500  → hit_rate=0.70, mrr=0.50, ndcg=0.58
Run 3: hierarchical chunk_size=800  → hit_rate=0.80, mrr=0.62, ndcg=0.71
```

> `mlruns/`는 `.gitignore`에 포함 (커밋 대상 아님). 실험 데이터는 로컬에만 저장.

---

## 4. 배포 전 정리 (main 병합 시 삭제)

- [ ] `test/` — 실험 스크립트
- [ ] `plan.md` — 개발 문서
- [ ] `services/callback.py` — 콜백 전송 (보류 상태)

---

## 의존성 참고

| 패키지 | 용도 | 필수/선택 |
|---|---|---|
| `httpx` | RunPod API 호출 | 필수 |
| `langchain-text-splitters` | 청킹 전략 | 필수 |
| `langchain-postgres` | PGVector 적재 | 필수 |
| `tiktoken` | S2 TokenChunker | 실험 |
| `langchain-experimental` | S3 SemanticChunker | 실험 |
| `langchain-huggingface` | S3 SemanticChunker | 실험 |
| `openai` (OPENAI_API_KEY) | S7 Contextual Retrieval | 실험 |
