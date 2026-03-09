# embedding/output

## 사용 모델

| 모델 | 차원 | 특징 |
|---|---|---|
| BAAI/bge-m3 | 1024 | 다국어, 8192 토큰, dense+sparse |
| intfloat/multilingual-e5-large | 1024 | 다국어, 512 토큰, query prefix 필요 |

## 사용 청킹 전략

| 전략 | 출처 |
|---|---|
| MD구분자_Markdown_1000c | chunking/output/ |
| 재귀분할_Recursive_500c | chunking/output/ |

## 디렉토리 구조

```
embedding/output/
├── {모델명}/
│   └── {전략명}/
│       ├── embeddings.json   ← 벡터 포함 전체 결과
│       ├── summary.json      ← 속도/차원 요약
│       ├── eval.json         ← 품질 평가 (분포, 클러스터링, 중복)
│       └── umap.png          ← UMAP 2D 시각화
├── total_analysis.md         ← 수치 비교 요약 (UMAP 제외)
└── README.md
```

## 평가 항목

벡터 자체의 품질만 측정합니다. Retrieval 성능 평가는 retriever/에서 별도 수행합니다.

- **분포**: 코사인 유사도 분포 (평균/std) — 변별력 확인
- **등방성 (Isotropy)**: 벡터 공간 활용도 — 1.0에 가까울수록 균등 분포
- **클러스터링 (Silhouette)**: source_id 기준 — 같은 문서 청크끼리 뭉치는 정도
- **중복 검출**: 코사인 유사도 0.95 이상 near-duplicate 쌍
- **UMAP 시각화**: 2D 산점도 (주관적 판단용, total_analysis에 미포함)
