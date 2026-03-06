# Data 서버 작업 계획

> 범위: 크롤링 → 청킹 → 임베딩 → 벡터 적재 → `/embed/query` 벡터 반환까지
> Retriever 검색, Reranker, top_k 처리는 백엔드에서 진행

## 1. API 연동 (완료)

- [X] `POST /crawl` — URL 수신 → 즉시 응답(`accepted`) → 백그라운드 크롤링·청킹·임베딩
- [X] `POST /embed/query` — 쿼리 텍스트 → 임베딩 벡터 반환
- [X] `GET /health` — 서버 상태 확인
- [X] 글로벌 예외 핸들러 (422 + 500)
- [X] `source.status` 컬럼 (pending → success/failed) 크롤링 상태 추적
- [X] 비동기 파이프라인 — URL별 독립 처리, 하나 실패해도 나머지 진행

## 2. 실험 (진행 중)

> API 연동은 완료 상태. 이제 최적의 청킹 × 임베딩 조합을 찾는 실험만 진행하면 된다.
> 실험 결과를 바탕으로 `chunk/config.py`, `embed/config.py`만 수정하면 파이프라인 반영 완료.
> 상세 실험 계획: `retriever-plan.md` 참조

- [ ] Phase 1: 청킹 전략 비교 (bge-m3 고정)
- [ ] Phase 2: 상위 전략 사이즈 튜닝
- [ ] Phase 3: 임베딩 모델 비교
- [ ] 최종 조합 확정 → `chunk/config.py`, `embed/config.py` 반영

### 실험 흐름

```
1. test/test_crawl.py    → source DB 적재 (크롤링 데이터 준비)
2. test/test_ce.py       → 전략·모델·사이즈 변경하며 page_data 적재
3. test/evaluation_ir.py → IR 지표 자동 평가 (MLflow에 기록)
4. mlflow ui             → 실험 결과 비교
```

### 실험 도구

| 도구 | 용도 |
|---|---|
| `test/test_crawl.py` | 크롤링 → source DB 적재 |
| `test/test_ce.py` | 청킹 + 임베딩 → page_data 적재 (전략·모델·사이즈 변경) |
| `test/evaluation_ir.py` | IR 지표 자동 평가 — Hit Rate, MRR, NDCG (MLflow 기록) |
| MLflow | 실험 기록·비교 (`mlflow-guide.md` 참조) |

## 3. 배포 전 정리 (main 병합 시 삭제)

- [ ] `test/` — 실험 스크립트 (크롤링, 청킹, 임베딩, 평가, 리랭커)
- [ ] `mlflow-guide.md`, `retriever-plan.md`, `plan.md` — 개발 문서
- [ ] `services/callback.py` — 콜백 전송 (보류 상태)
