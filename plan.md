# Data 서버 작업 계획

> 범위: 크롤링 → 청킹 → 임베딩 → 벡터 적재 → `/embed/query` 벡터 반환까지
> Retriever 검색, Reranker, top_k 처리는 백엔드에서 진행

## 1. 통합 실험 파이프라인

- [X] 청킹 전략 비교 (`chunk/run_experiment.py`)
- [X] 임베딩 모델 비교 (`embed/run_test.py`)
- [X] 임베딩 품질 평가 (`embed/evaluation.py`)
- [ ] 최종 청킹 × 임베딩 조합 확정 → 서비스 코드 반영

## 2. Pipeline 안정성

- [X] `GET /health` 엔드포인트
- [X] 글로벌 예외 핸들러 (500 + 422)
- [~] 콜백 재시도 로직 — 코드 구현 완료, 연동 보류
- [~] 에러 콜백 전송 (`services/callback.py`) — 코드 구현 완료, 연동 보류

## 3. API 연동

- [X] `POST /crawl` — 크롤링 + 백그라운드 ETL
- [X] `POST /embed/query` — 쿼리 텍스트 → 임베딩 벡터 반환
- [ ] API 통합 테스트 (pytest + TestClient)

## 4. 성능 고도화

> 상세 실험 계획: `retriever-plan.md` 참조

- [ ] 평가 체계 전환: RAGAS → 커스텀 IR 지표 (Hit Rate, MRR, NDCG)
- [ ] MLflow 실험 추적 도입
- [ ] Baseline vs Reranker 비교 측정 (실험용 — 서비스 reranker는 backend 담당)
- [ ] 청킹 변수 실험 (chunk_size / overlap 조합 테스트)
- [ ] 임베딩 모델 추가 비교 (OpenAI text-embedding-3 등) — 기본 세팅 완료 후 동일 조건에서 진행
- [ ] 추후 LLM 프롬프트 도입 시 deepeval 확장 (Answer Relevancy, Faithfulness 등)

## 5. 배포 전 정리 (main 병합 시 삭제)

- [ ] `retriever/` — 평가 전용 코드 (evaluation.py, evaluation_ir.py, metrics.py, reranker.py, testset.json, config.py, service.py, output/)
- [ ] `test_crawl.py` — 수동 크롤링 테스트
- [ ] `test_ce.py` — 청킹+임베딩 실험 테스트
- [ ] `retriever_test.py` — 수동 검색 테스트
- [ ] `mlflow-guide.md`, `retriever-plan.md`, `plan.md` — 개발 문서
