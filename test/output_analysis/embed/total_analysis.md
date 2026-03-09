# 임베딩 벡터 품질 분석 요약

> 벡터 자체의 분포·등방성·클러스터링·중복도만 평가합니다.
> Retrieval 성능 평가는 retriever/ 에서 별도 수행합니다.

## 분포 & 등방성

| 모델 × 전략 | cos 평균 | cos std | Isotropy |
|---|---|---|---|
| BAAI_bge-m3 / MD구분자_Markdown_1000c | 0.4042 | 0.0764 | 415.3634 |
| BAAI_bge-m3 / 재귀분할_Recursive_500c | 0.3968 | 0.0733 | 534.8079 |
| intfloat_multilingual-e5-large / MD구분자_Markdown_1000c | 0.8377 | 0.0354 | 333.5893 |
| intfloat_multilingual-e5-large / 재귀분할_Recursive_500c | 0.822 | 0.0378 | 452.9866 |
| BAAI_bge-m3 / 토큰기반_Token_256tok | 0.396 | 0.0737 | 536.9027 |
| intfloat_multilingual-e5-large / 토큰기반_Token_256tok | 0.8459 | 0.0316 | 434.5249 |

## 클러스터링 (Silhouette, source_id 기준)

| 모델 × 전략 | Silhouette | 클러스터 수 |
|---|---|---|
| BAAI_bge-m3 / MD구분자_Markdown_1000c | 0.1454 | 121 |
| BAAI_bge-m3 / 재귀분할_Recursive_500c | 0.1045 | 121 |
| intfloat_multilingual-e5-large / MD구분자_Markdown_1000c | 0.166 | 121 |
| intfloat_multilingual-e5-large / 재귀분할_Recursive_500c | 0.1042 | 121 |
| BAAI_bge-m3 / 토큰기반_Token_256tok | 0.1233 | 121 |
| intfloat_multilingual-e5-large / 토큰기반_Token_256tok | 0.1463 | 121 |

## 중복 검출

| 모델 × 전략 | threshold | 중복 쌍 | 중복 비율 |
|---|---|---|---|
| BAAI_bge-m3 / MD구분자_Markdown_1000c | 0.95 | 5/735 | 0.0 |
| BAAI_bge-m3 / 재귀분할_Recursive_500c | 0.95 | 16/1478 | 0.0 |
| intfloat_multilingual-e5-large / MD구분자_Markdown_1000c | 0.95 | 272/735 | 0.001 |
| intfloat_multilingual-e5-large / 재귀분할_Recursive_500c | 0.95 | 360/1478 | 0.0003 |
| BAAI_bge-m3 / 토큰기반_Token_256tok | 0.95 | 15/1578 | 0.0 |
| intfloat_multilingual-e5-large / 토큰기반_Token_256tok | 0.95 | 1063/1578 | 0.0009 |

## 해석 가이드

- **cos 평균**: 낮을수록 벡터 간 변별력 높음 (0.3~0.5 권장)
- **cos std**: 높을수록 유사도 분포가 넓음 (변별력 있음)
- **Isotropy**: 1.0에 가까울수록 벡터 공간을 고르게 활용
- **Silhouette**: 1.0에 가까울수록 같은 source 청크끼리 잘 뭉침
- **중복 비율**: 낮을수록 좋음 (높으면 DB 저장 전 제거 필요)