# IR 평가 결과 분석

## 실험 조건

| 항목 | 값 |
|---|---|
| 임베딩 모델 | BAAI/bge-m3 |
| 테스트셋 | testset.json (50개 질문) |
| 관련성 판정 | 키워드 매칭 (threshold=0.4) |

---

## 실험 결과

### 1. semantic_auto / baseline / top_k=5

| 지표 | 결과 | 평가 |
|---|---|---|
| Hit Rate | 0.617 | 질문의 38%에서 관련 문서를 못 찾음 |
| MRR | 0.536 | 관련 문서가 평균 2위 근처 |
| NDCG | 0.555 | 순위 품질 보통 |
| Precision@5 | 0.204 | 5건 중 1건 정도만 관련 |
| Recall@5 | 0.204 | 관련 문서 대부분 놓침 |

---

## 분석

### 현재 성능 수준

- Hit Rate 0.62는 **낮은 편**. 10개 질문 중 4개에서 관련 문서를 전혀 찾지 못함
- Precision/Recall 0.20은 top-5 중 평균 1개만 관련 → 노이즈가 많음
- MRR 0.54는 관련 문서가 있어도 1위가 아닌 경우가 많음

### 개선 방향

1. **리랭커 적용** (`--mode reranker`): 벡터 검색 top-20 → Cross-Encoder 재정렬 → top-5
2. **청킹 전략 변경**: SemanticChunker 외 MarkdownChunker 등 비교
3. **top_k 증가**: top_k=10으로 재실험하여 recall 변화 확인
4. **관련성 판정 개선**: 키워드 threshold 조정 또는 LLM 기반 판정

---

*이 분석은 키워드 매칭 기반 관련성 판정으로 산출되었습니다. 실제 체감 품질은 test_response.py로 확인하세요.*
