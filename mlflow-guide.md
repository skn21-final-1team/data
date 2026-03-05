# MLflow 사용 가이드

## 설치

```bash
uv sync --extra dev
```

## 평가 실행

```bash
# baseline
uv run python -m retriever.evaluation_ir --mode baseline --top_k 5

# reranker
uv run python -m retriever.evaluation_ir --mode reranker --top_k 5
```

실행 시 자동으로 `mlruns/` 폴더에 실험 기록이 저장된다.

## MLflow UI 실행

```bash
uv run mlflow ui --port 5000
```

브라우저에서 `http://localhost:5000` 접속.

## UI 사용법

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
Run 1: baseline, chunk_size=1000 → hit_rate=0.65, mrr=0.45, ndcg=0.52
Run 2: reranker, chunk_size=1000 → hit_rate=0.80, mrr=0.62, ndcg=0.71
Run 3: baseline, chunk_size=500  → hit_rate=0.70, mrr=0.50, ndcg=0.58
```

## 참고

- `mlruns/`는 `.gitignore`에 포함되어 있음 (커밋 대상 아님)
- 실험 데이터는 로컬에만 저장됨
- `retriever/output/`에도 동일한 결과가 JSON으로 저장됨
