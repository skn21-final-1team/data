# 임베딩 벡터 품질 분석

## 사용 모델

| 모델 | 차원 | 특징 |
|---|---|---|
| BAAI/bge-m3 | 1024 | 다국어, 8192 토큰, dense+sparse |

## 디렉토리 구조

```
test/output/{전략라벨}/{사이즈}_{오버랩}/
├── chunks.json        ← test_chunk.py 산출
└── embeddings.json    ← test_embed.py 산출 (분석 후 삭제 가능)

test/output_analysis/embed/
├── comparison.csv     ← 수치 비교 (test_embed_analysis.py 산출)
├── total_analysis.md  ← 요약 리포트
└── README.md
```

## 실행 방법

```bash
# 1) 임베딩 생성
uv run python -m test.test_embed --strategy S5_MD구분자_Markdown --size 256_30

# 2) 전체 분석 (embeddings.json이 있는 모든 전략 대상)
uv run python -m test.test_embed_analysis

# 3) 특정 전략만 분석
uv run python -m test.test_embed_analysis --strategy S5_MD구분자_Markdown --size 256_30
```

## 평가 항목

벡터 자체의 품질만 측정합니다. Retrieval 성능 평가는 별도 수행합니다.

| 지표 | 의미 | 판단 기준 |
|---|---|---|
| cos_mean | 벡터 간 코사인 유사도 평균 | 낮을수록 변별력 높음 (0.3~0.5 권장) |
| cos_std | 코사인 유사도 표준편차 | 높을수록 유사도 분포가 넓음 |
| isotropy | 벡터 공간 활용도 | 1.0에 가까울수록 균등 분포 |
| silhouette | source_id 기준 클러스터링 | 1.0에 가까울수록 같은 문서 청크끼리 뭉침 |
| dup_pairs | cos >= 0.95 near-duplicate 쌍 수 | 적을수록 좋음 |
| dup_ratio | 중복 비율 | 낮을수록 좋음 (높으면 DB 저장 전 제거 필요) |

## 전략 선택 가이드

1. **cos_mean 낮은 것** — 벡터 변별력 확인
2. **silhouette 높은 것** — 같은 문서 청크끼리 잘 뭉치는지
3. **dup_ratio 낮은 것** — 불필요한 중복 없는지
4. 2~3개 후보를 추리고, 최종 판단은 retrieval 성능으로 결정
