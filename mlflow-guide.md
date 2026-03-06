# MLflow 실험 가이드

## 설치

```bash
uv sync --extra dev
```

---

## 전체 실험 순서

### Step 1 — 크롤링 데이터 준비

```bash
uv run python -m test.test_crawl 27
```

### Step 2 — 청킹 + 임베딩 → DB 적재

전략·사이즈를 변경할 때마다 `--clear` 옵션으로 재적재:

```bash
# 기본 설정 (markdown / bge-m3 / 1000 / 100)
uv run python -m test.test_ce 27 --test --clear

# 전략 변경 예시
uv run python -m test.test_ce 27 --test --clear --strategy recursive --chunk_size 500 --chunk_overlap 50
```

사용 가능한 전략: `recursive` / `token` / `semantic` / `markdown_header` / `markdown` / `hierarchical`

사용 가능한 임베딩: `bge-m3` / `e5-large`

### Step 3 — IR 평가 실행 (MLflow 자동 기록)

```bash
uv run python -m test.evaluation_ir --mode reranker --top_k 5
```

실행 시 `mlruns/` 폴더에 실험 결과가 자동 저장된다.

### Step 4 — MLflow UI로 결과 비교

```bash
uv run mlflow ui --port 5000
```

브라우저에서 `http://localhost:5000` 접속.

---

## MLflow UI 사용법

### 실험 목록 확인

1. 좌측 사이드바 → `retriever-evaluation` 실험 선택
2. 각 run의 params와 metrics 확인 가능

### 기록되는 항목

| 구분 | 항목 |
|---|---|
| **params** | embed_model, chunk_strategy, chunk_size, chunk_overlap, mode, top_k |
| **metrics** | hit_rate, mrr, ndcg |
| **artifacts** | results.json, details.json |

### 실험 비교

1. 비교할 run들을 체크박스로 선택
2. **Compare** 버튼 클릭
3. 차트/테이블로 params와 metrics 비교

### 예시 흐름

```
Run 1: markdown,    chunk_size=1000 → hit_rate=0.65, mrr=0.45, ndcg=0.52
Run 2: recursive,   chunk_size=500  → hit_rate=0.70, mrr=0.50, ndcg=0.58
Run 3: hierarchical chunk_size=800  → hit_rate=0.80, mrr=0.62, ndcg=0.71
```

---

## 참고

- `mlruns/`는 `.gitignore`에 포함되어 있음 (커밋 대상 아님)
- 실험 데이터는 로컬에만 저장됨
- `test/output/`에도 동일한 결과가 JSON으로 저장됨
- 상세 실험 변수 및 Phase 계획: `retriever-plan.md` 참조

