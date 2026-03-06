# Retriever 실험 계획

## 테스트 환경

- testset.json: 20개 질문 (단일 15 + 복합 5)
- notebook_id: 27
- URL: 31개 (test.py)
- mode: reranker 고정 (벡터검색 top-20 → bge-reranker-v2-m3 → top-5)

## 평가 지표

### 현재 (임베딩 비교 단계)

LLM 호출 없이 동작하는 IR 지표 사용 (비용 0):

| 지표 | 설명 |
|---|---|
| Hit Rate@5 | 정답 chunk가 top-5 안에 존재하는 비율 |
| MRR | 첫 번째 정답 chunk의 순위 역수 평균 |
| NDCG@5 | 순위 품질 (상위 배치에 가중치) |

### 추후 (LLM 프롬프트 도입 시)

deepeval 도입하여 LLM 기반 지표 추가:

| 지표 | 설명 |
|---|---|
| Answer Relevancy | 생성된 답변이 질문과 관련 있는지 |
| Faithfulness | 답변이 context에 근거하는지 |
| Contextual Relevancy | 검색된 context가 질문에 적합한지 |

---

## 실험 변수

### A. 임베딩 모델 (3종)

| ID | 모델 | 차원 | 비고 |
|---|---|---|---|
| E1 | `BAAI/bge-m3` | 1024 | 현재 서비스 기본 모델 |
| E2 | `intfloat/multilingual-e5-large` | 1024 | 기존 비교 모델 |
| E3 | `OpenAI/text-embedding-3-large` | 3072 | API 기반, 기본 세팅 완료 후 진행 |

### B. 청킹 전략 (11종)

**기존 전략 (6종)**

| ID | 전략 | 설명 |
|---|---|---|
| S1 | RecursiveChunker | 재귀적 문자 분할 (베이스라인) |
| S2 | TokenChunker | 토큰 기반 분할 (tiktoken cl100k_base) |
| S3 | SemanticChunker | 임베딩 유사도 기반 의미 분할 |
| S4 | MarkdownHeaderChunker | 헤더 기반 구조 분할 (H1/H2/H3) |
| S5 | MarkdownChunker | MD 구분자 + Recursive 분할 (현재 서비스) |
| S6 | HierarchicalMarkdownChunker | 1차 헤더 분할 → 2차 Recursive 재분할 |

**헤더 경로 Prepend 변형 (2종)**

| ID | 전략 | 설명 |
|---|---|---|
| S5-P | MarkdownChunker + Prepend | S5에 헤더 경로 주입 (`[# A > ## B > ### C] 본문...`) |
| S6-P | HierarchicalMarkdownChunker + Prepend | S6에 헤더 경로 주입 |

> 헤더 경로 Prepend: 각 chunk 앞에 해당 문단이 속한 헤더 경로를 문자열로 주입.
> LLM 없이 문서 구조만으로 맥락을 복원하는 저비용 기법.
> 예: `[일론 머스크 > 초기 생애 > 남아프리카] 프리토리아에서 1971년에 태어났다.`

**고급 전략 (3종)**

| ID | 전략 | 설명 | 비고 |
|---|---|---|---|
| S7 | Contextual Retrieval | chunk에 LLM이 생성한 맥락 요약을 prepend | LLM 호출 비용 발생 |
| S8 | Late Chunking | 임베딩 후 분할 (토큰 레벨 임베딩 → 구간 평균) | 모델 아키텍처 의존, 구현 난이도 높음 |
| S9 | Sentence Window | 문장 단위 분할 + 검색 시 주변 문장 확장 | 검색 시 확장 로직 필요 |

> S3: size/overlap 고정 불가 (임베딩 유사도로 자동 분할)
> S4: size/overlap 고정 불가 (헤더 기준 분할)

### C. 청킹 사이즈 / 오버랩 조합

| ID | chunk_size | chunk_overlap | 비율 |
|---|---|---|---|
| C1 | 256 | 30 | 11.7% |
| C2 | 500 | 50 | 10.0% |
| C3 | 800 | 100 | 12.5% |
| C4 | 1000 | 100 | 10.0% (현재) |
| C5 | 1000 | 200 | 20.0% |
| C6 | 1500 | 150 | 10.0% |
| C7 | 2000 | 200 | 10.0% |

### D. 검색 설정 (고정)

| 항목 | 값 |
|---|---|
| mode | reranker |
| 벡터검색 top_k | 20 |
| rerank 후 top_k | 5 |
| reranker 모델 | bge-reranker-v2-m3 |

---

## 실험 매트릭스

### Phase 1: 청킹 전략 비교 (E1 고정, 사이즈 고정)

임베딩 모델 `BAAI/bge-m3` 고정, 각 전략의 기본 사이즈로 비교:

| # | 전략 | chunk_size | overlap | hit_rate | mrr | ndcg |
|---|---|---|---|---|---|---|
| 1-1 | S1 RecursiveChunker | 500 | 50 | | | |
| 1-2 | S2 TokenChunker | 256tok | 30tok | | | |
| 1-3 | S3 SemanticChunker | auto | auto | | | |
| 1-4 | S4 MarkdownHeaderChunker | auto | auto | | | |
| 1-5 | S5 MarkdownChunker | 1000 | 100 | | | |
| 1-6 | S6 HierarchicalMarkdownChunker | 1000 | 100 | | | |
| 1-7 | S5-P MarkdownChunker + Prepend | 1000 | 100 | | | |
| 1-8 | S6-P HierarchicalMarkdownChunker + Prepend | 1000 | 100 | | | |

### Phase 2: 최적 전략의 사이즈 튜닝

Phase 1에서 상위 2~3개 전략 선정 → 사이즈 조합 테스트:

| # | 전략 | chunk_size | overlap | hit_rate | mrr | ndcg |
|---|---|---|---|---|---|---|
| 2-1 | (상위 전략) | 256 | 30 | | | |
| 2-2 | (상위 전략) | 500 | 50 | | | |
| 2-3 | (상위 전략) | 800 | 100 | | | |
| 2-4 | (상위 전략) | 1000 | 100 | | | |
| 2-5 | (상위 전략) | 1000 | 200 | | | |
| 2-6 | (상위 전략) | 1500 | 150 | | | |
| 2-7 | (상위 전략) | 2000 | 200 | | | |

### Phase 3: 임베딩 모델 비교

Phase 2에서 확정된 최적 전략 + 사이즈로 임베딩 모델 비교:

| # | 모델 | 전략 | size | overlap | hit_rate | mrr | ndcg |
|---|---|---|---|---|---|---|---|
| 3-1 | E1 BAAI/bge-m3 | (확정) | (확정) | (확정) | | | |
| 3-2 | E2 multilingual-e5-large | (확정) | (확정) | (확정) | | | |
| 3-3 | E3 text-embedding-3-large | (확정) | (확정) | (확정) | | | |

> **E3 주의**: `EMBEDDING_DIMENSION=1024`로 하드코딩 + HNSW 인덱스가 1024차원에 맞춰져 있음.
> E3(3072차원) 테스트 시 `models/page_data.py` 차원 변경 + DB 마이그레이션(인덱스 재생성) 필요.
> E1, E2는 둘 다 1024차원이므로 스키마 변경 없이 전환 가능.

### Phase 4: 고급 청킹 전략 (선택)

기본 실험 완료 후 필요 시 진행:

| # | 전략 | 비고 | hit_rate | mrr | ndcg |
|---|---|---|---|---|---|
| 4-1 | S7 Contextual Retrieval | LLM 호출 비용 발생 | | | |
| 4-2 | S8 Late Chunking | 구현 난이도 높음 | | | |
| 4-3 | S9 Sentence Window | 검색 시 확장 로직 필요 | | | |

---

## 실험 실행 방법

### 0. 공통 전제

```bash
# 프로젝트 루트(data/)에서 실행
# DB에 notebook_id=27의 source 데이터가 있어야 함
```

### 1. 데이터 준비 (최초 1회 또는 새 데이터 필요 시)

```bash
uv run python -m test.test_crawl 27
```

### 2. 청킹 + 임베딩 → page_data 적재

전략·모델·사이즈를 변경하며 반복 실행:

```bash
# 기본 (markdown / bge-m3 / 1000 / 100) — 테스트 테이블 적재
uv run python -m test.test_ce 27 --test --clear

# 전략 변경 예시
uv run python -m test.test_ce 27 --test --clear --strategy recursive --chunk_size 500 --chunk_overlap 50
uv run python -m test.test_ce 27 --test --clear --strategy hierarchical --chunk_size 800 --chunk_overlap 100

# 임베딩 모델 변경 예시
uv run python -m test.test_ce 27 --test --clear --embed_model e5-large
```

> **주의**: 전략·사이즈가 바뀔 때마다 `--clear`로 기존 데이터를 삭제하고 재적재해야 한다.

### 3. IR 지표 평가 → MLflow 기록

```bash
uv run python -m test.evaluation_ir --mode reranker --top_k 5
```

실행 시 `mlruns/`에 자동 기록. 한 Phase가 끝나면 MLflow UI에서 비교.

### 4. MLflow UI로 비교

```bash
uv run mlflow ui --port 5000
# http://localhost:5000 → retriever-evaluation 실험 선택 → Compare
```

MLflow 상세 사용법: `mlflow-guide.md` 참조

---

## 의존성

- `mlflow` → dev 의존성 추가 완료
- 기존 `ragas`, `datasets` → 평가 전환 완료 후 제거 예정
- 추후 `deepeval` → LLM 프롬프트 도입 시 dev 의존성 추가
- E3 (OpenAI) 사용 시 `openai` 패키지 + API 키 필요

