# 모델링 및 평가 테스트 계획 및 결과 보고서

## 목차

1. [개요](#1-개요)
2. [평가 방법론](#2-평가-방법론)
3. [리트리버 품질 평가](#3-리트리버-품질-평가)
4. [대화 품질 평가](#4-대화-품질-평가)
5. [보고서 품질 평가](#5-보고서-품질-평가)
6. [결론](#6-결론)

---

## 1. 개요

### 1.1 보고서 목적

본 보고서는 RAG(Retrieval-Augmented Generation) 파이프라인의 전 단계별 품질을 정량적으로 평가하고, 최적 구성을 도출하기 위한 실험 계획과 결과를 정리한다.

### 1.2 평가 대상

| 평가 영역 | 설명 | 담당 |
|---|---|---|
| 리트리버 품질 | 임베딩 모델 x 청킹 전략 x 리랭커 조합의 검색 성능 | data |
| 대화 품질 | 사용자 질문에 대한 LLM 응답의 정확성, 자연스러움, 근거 충실도 | backend |
| 보고서 품질 | 저장된 내용 기반 보고서 생성의 사용자 목적 부합도 | backend |

### 1.3 파이프라인 아키텍처

```
Backend                              Data 서버
  │                                    │
  │  source 레코드 생성 (인증/보안)     │
  │  POST /crawl                       │
  │  {sources: [{source_id, url}]}     │
  │ ──────────────────────────────────→│
  │                                    │
  │                              [Phase 1: 크롤링 (순차)]
  │                              크롤링 → raw 저장
  │                                    │
  │                              [Phase 2: LLM + 임베딩 (병렬)]
  │                              전처리(Markdown) → vLLM 정제 → vLLM 요약
  │                                    │
  │  ← callback: summary_completed ────│  Frontend에 summary 표시
  │                                    │
  │                              헤더 기반 청킹 → 임베딩 → PGVector 저장
  │                                    │
  │  ← callback: embed_completed ──────│  질문 검색 활성화
  │                                    │
  │                              [실패 시 순번 밀기 재시도 (최대 2회)]
  │  ← callback: retrying / failed ────│
  │                                    │
  │          사용자 질의 → 벡터 검색(top_k) → LLM 응답 생성
```

### 1.4 테스트셋

- **질문 수**: 47개 (단일 소스 질문 30개 + 복합 소스 질문 17개)
- **notebook_id**: 21 (기준), `--notebook_id`로 전환 가능
- **구성**: `{"question", "ground_truth", "notebook_id"}`
- 각 질문에 대해 사람이 직접 작성한 ground_truth 기반으로 평가

---

## 2. 평가 방법론

### 2.1 평가 프레임워크 선정

본 프로젝트는 **RAGAS 논문**(Es et al., 2023)이 제안한 Contextual Precision, Contextual Recall, Contextual Relevancy 지표를 채택하였으며, 평가 프레임워크로는 동일 방법론을 구현하면서 CI/CD 통합과 다단계 평가 확장성이 우수한 **DeepEval**을 사용하였다.

| 항목 | 내용 |
|---|---|
| 평가 방법론 | RAGAS (Retrieval Augmented Generation Assessment) |
| 구현 프레임워크 | DeepEval |
| LLM Judge | OpenAI gpt-4o-mini |
| 실험 추적 | MLflow |

### 2.2 DeepEval 선정 근거

| 비교 항목 | DeepEval | RAGAS 라이브러리 |
|---|---|---|
| 평가 방법론 | RAGAS 논문 동일 | RAGAS 논문 동일 |
| LangChain 의존성 | 없음 (독립 실행) | 강하게 결합 |
| 확장성 | 리트리버 + 응답 + 보고서 평가 통합 가능 | 리트리버 평가 특화 |
| CI/CD 통합 | pytest 네이티브 지원 | 별도 구현 필요 |
| 버전 안정성 | 안정적 API | 버전 간 breaking change 빈번 |

본 프로젝트는 리트리버 품질(data) → 대화 품질(backend) → 보고서 품질(backend)로 평가 범위가 확장되므로, 세 단계를 하나의 프레임워크로 커버할 수 있는 DeepEval이 적합하다.

### 2.3 평가 지표

| 지표 | 측정 대상 | ground_truth 사용 | 설명 |
|---|---|---|---|
| **Contextual Precision** | 순위 품질 | O | 관련 context가 상위 순위에 있는가 |
| **Contextual Recall** | 정보 커버리지 | O | ground_truth에 필요한 정보를 context가 얼마나 포함하는가 |
| **Contextual Relevancy** | 노이즈 비율 | X | 검색된 context 중 질문에 관련있는 비율 |

세 지표로 리트리버의 **순위 / 커버리지 / 노이즈** 세 축을 모두 평가한다.

#### 지표 우선순위: Recall > Precision > Relevancy

리트리버 성능 판단 시 세 지표의 중요도는 동일하지 않다. RAG 파이프라인 특성상 다음 순서로 우선시한다.

| 순위 | 지표 | 이유 |
|---|---|---|
| 1 | **Contextual Recall** | 필요한 정보가 검색되지 않으면 LLM이 아예 답변할 수 없다. 누락은 보완 불가능하므로 가장 치명적이다. |
| 2 | **Contextual Precision** | 관련 context가 상위에 위치해야 top_k가 작을 때도 핵심 정보를 놓치지 않는다. 순위가 나쁘면 top_k 축소 시 성능이 급락한다. |
| 3 | **Contextual Relevancy** | 노이즈(무관한 청크)는 LLM 응답 품질을 저하시키지만, 리랭커 적용으로 개선 가능하다. 세 지표 중 후처리로 보완할 여지가 가장 크다. |

**해석 가이드**:
- Recall이 낮다면 → 청킹 전략 또는 임베딩 모델 변경이 필요 (근본적 문제)
- Recall은 높은데 Precision이 낮다면 → 검색은 되지만 순위가 나쁨, 리랭커로 개선 가능
- Recall/Precision은 높은데 Relevancy가 낮다면 → 노이즈 존재, 리랭커 적용이 효과적

### 2.4 평가 프로세스

```
질문 → 벡터 검색(top_k=5) → [Reranker] → 검색된 chunks
                                              ↓
                            DeepEval (gpt-4o-mini) → Contextual Precision/Recall/Relevancy
                                              ↓
                            결과 저장 (results.json, details.json) + MLflow 기록
```

---

## 3. 리트리버 품질 평가

### 3.1 실험 설계

#### 3.1.1 독립변수

| 변수 | 후보 | 비고 |
|---|---|---|
| 임베딩 모델 | BAAI/bge-m3, Qwen3-Embedding | bge-m3: 다국어 지원, Qwen3: 한국어 강점 |
| 청킹 전략 | Semantic Auto, Contextual (gpt-4o-mini), HierarchicalPrepend | 임베딩 기반 / LLM 기반 / 구조 기반 |
| 리랭커 | 없음(Baseline), bge-reranker-v2-m3 (RunPod) | Cross-Encoder 기반 재정렬 |

#### 3.1.2 청킹 전략 상세

| 전략 | 접근 방식 | chunk_size | chunk_overlap | 특징 |
|---|---|---|---|---|
| Semantic Auto | 임베딩 유사도 기반 경계 탐지 | 자동 | 자동 | 자동 분할, 추가 비용 없음 |
| Contextual (S7) | 마크다운 분할 + gpt-4o-mini 맥락 요약 prepend | 800 | 100 | LLM 요약이 +100자 추가됨 |
| HierarchicalPrepend (S6-P) | 헤더 기반 분할 + 재귀 분할 + 헤더 경로 prepend | 1000 | 150 | 문서 구조 활용, 비용 없음 |

#### 3.1.3 실험 매트릭스 (총 12개 실험, 12/12 완료)

| # | 임베딩 모델 | 청킹 전략 | 리랭커 | 상태 |
|---|---|---|---|---|
| 1 | bge-m3 | Semantic Auto | Baseline | **완료** |
| 2 | bge-m3 | Contextual (800/100) | Baseline | **완료** |
| 3 | bge-m3 | HierarchicalPrepend (1000/150) | Baseline | **완료** |
| 4 | bge-m3 | Semantic Auto | Reranker | **완료** |
| 5 | bge-m3 | Contextual | Reranker | **완료** |
| 6 | bge-m3 | HierarchicalPrepend | Reranker | **완료** |
| 7 | Qwen3 | Semantic Auto | Baseline | **완료** |
| 8 | Qwen3 | Contextual | Baseline | **완료** |
| 9 | Qwen3 | HierarchicalPrepend | Baseline | **완료** |
| 10 | Qwen3 | Semantic Auto | Reranker | **완료** |
| 11 | Qwen3 | Contextual | Reranker | **완료** |
| 12 | Qwen3 | HierarchicalPrepend | Reranker | **완료** |

#### 3.1.4 고정 조건

| 항목 | 값 |
|---|---|
| 테스트셋 | 47개 질문 |
| top_k | 5 |
| Reranker fetch_k | 20 (벡터검색 top-20 → 리랭크 top-5) |
| DeepEval 모델 | gpt-4o-mini |
| DB | PostgreSQL + PGVector (langchain-postgres) |
| Reranker 인프라 | RunPod Serverless (GPU) |

### 3.2 실험 결과

#### 3.2.1 bge-m3 — Baseline

| 청킹 전략 | C.Precision | C.Recall | C.Relevancy |
|---|---|---|---|
| Semantic Auto | 0.8822 | 0.9087 | 0.5811 |
| Contextual (800/100) | 0.8888 | **0.9344** | 0.5873 |
| HierarchicalPrepend (1000/150) | 0.8893 | 0.8972 | 0.5844 |

#### 3.2.2 bge-m3 — Reranker

| 청킹 전략 | C.Precision | C.Recall | C.Relevancy |
|---|---|---|---|
| Semantic Auto | 0.9189 | 0.9326 | 0.5983 |
| Contextual (800/100) | 0.8941 | 0.9326 | 0.5929 |
| **HierarchicalPrepend (1000/150)** | **0.9255** | **0.9326** | **0.6063** |

#### 3.2.3 Qwen3 — Baseline

| 청킹 전략 | C.Precision | C.Recall | C.Relevancy |
|---|---|---|---|
| Semantic Auto | 0.8129 | 0.8650 | 0.3246 |
| Contextual (800/100) | 0.8351 | **0.9255** | 0.5675 |
| HierarchicalPrepend (1000/150) | 0.8364 | 0.9043 | 0.5519 |

#### 3.2.4 Qwen3 — Reranker

| 청킹 전략 | C.Precision | C.Recall | C.Relevancy |
|---|---|---|---|
| Semantic Auto | 0.8634 | 0.8617 | 0.2800 |
| Contextual (800/100) | **0.9082** | **0.9326** | 0.5467 |
| HierarchicalPrepend (1000/150) | 0.8755 | 0.9016 | 0.5538 |

### 3.3 분석

#### 3.3.1 전체 결과 비교표

| # | 임베딩 모델 | 청킹 전략 | 리랭커 | C.Precision | C.Recall | C.Relevancy |
|---|---|---|---|---|---|---|
| 1 | bge-m3 | Semantic Auto | Baseline | 0.8822 | 0.9087 | 0.5811 |
| 2 | bge-m3 | Contextual | Baseline | 0.8888 | **0.9344** | 0.5873 |
| 3 | bge-m3 | HierarchicalPrepend | Baseline | 0.8893 | 0.8972 | 0.5844 |
| 4 | bge-m3 | Semantic Auto | Reranker | 0.9189 | 0.9326 | 0.5983 |
| 5 | bge-m3 | Contextual | Reranker | 0.8941 | 0.9326 | 0.5929 |
| **6** | **bge-m3** | **HierarchicalPrepend** | **Reranker** | **0.9255** | **0.9326** | **0.6063** |
| 7 | Qwen3 | Semantic Auto | Baseline | 0.8129 | 0.8650 | 0.3246 |
| 8 | Qwen3 | Contextual | Baseline | 0.8351 | 0.9255 | 0.5675 |
| 9 | Qwen3 | HierarchicalPrepend | Baseline | 0.8364 | 0.9043 | 0.5519 |
| 10 | Qwen3 | Semantic Auto | Reranker | 0.8634 | 0.8617 | 0.2800 |
| 11 | Qwen3 | Contextual | Reranker | 0.9082 | 0.9326 | 0.5467 |
| 12 | Qwen3 | HierarchicalPrepend | Reranker | 0.8755 | 0.9016 | 0.5538 |

#### 3.3.2 임베딩 모델 비교: bge-m3 vs Qwen3

| 비교 항목 | bge-m3 (6건 평균) | Qwen3 (6건 평균) | 차이 |
|---|---|---|---|
| C.Precision | 0.900 | 0.855 | bge-m3 +0.045 |
| C.Recall | 0.923 | 0.899 | bge-m3 +0.024 |
| C.Relevancy | 0.592 | 0.471 | bge-m3 +0.121 |

- **bge-m3가 모든 지표에서 Qwen3를 상회**한다
- Relevancy 격차가 가장 크다 (+0.121). Qwen3 Semantic Auto의 Relevancy가 0.32~0.28로 매우 낮아 **노이즈가 심하다**
- Qwen3는 Contextual/HierarchicalPrepend 적용 시 Relevancy가 0.55~0.57로 개선되지만, bge-m3(0.58~0.61) 대비 여전히 낮다
- Qwen3 + Contextual + Reranker에서 Precision 0.908로 Qwen3 최고치를 기록하나, bge-m3 + HierarchicalPrepend + Reranker(0.926)에는 미치지 못한다

#### 3.3.3 청킹 전략 비교

bge-m3 Baseline 기준:

| 청킹 전략 | C.Precision | C.Recall | C.Relevancy | 특징 |
|---|---|---|---|---|
| Semantic Auto | 0.8822 | 0.9087 | 0.5811 | 균형 잡힌 성능, 추가 비용 없음 |
| Contextual | 0.8888 | **0.9344** | 0.5873 | **최고 Recall**, LLM 비용 발생 |
| HierarchicalPrepend | 0.8893 | 0.8972 | 0.5844 | Precision 소폭 우위, 비용 없음 |

- **Recall 기준**: Contextual(0.934) > Semantic Auto(0.909) > HierarchicalPrepend(0.897)
- Contextual 전략이 LLM 맥락 요약을 prepend하여 **정보 커버리지가 가장 높다**
- 세 전략 간 Precision과 Relevancy 차이는 미미하다 (0.01 이내)

#### 3.3.4 리랭커 효과

bge-m3 기준 Baseline → Reranker 변화:

| 청킹 전략 | C.Precision 변화 | C.Recall 변화 | C.Relevancy 변화 |
|---|---|---|---|
| Semantic Auto | 0.882 → 0.919 (+0.037) | 0.909 → 0.933 (+0.024) | 0.581 → 0.598 (+0.017) |
| Contextual | 0.889 → 0.894 (+0.005) | 0.934 → 0.933 (-0.001) | 0.587 → 0.593 (+0.006) |
| HierarchicalPrepend | 0.889 → **0.926** (+0.037) | 0.897 → **0.933** (+0.036) | 0.584 → **0.606** (+0.022) |

- 리랭커는 **Precision 개선에 가장 효과적**이다 (Semantic Auto +0.037, HierarchicalPrepend +0.037)
- **HierarchicalPrepend + Reranker**에서 가장 큰 개선폭을 보인다 (세 지표 모두 최고값 달성)
- Contextual은 이미 Baseline에서 Recall이 높아 리랭커 추가 효과가 제한적이다

#### 3.3.5 Qwen3 리랭커 효과

Qwen3 기준 Baseline → Reranker 변화:

| 청킹 전략 | C.Precision 변화 | C.Recall 변화 | C.Relevancy 변화 |
|---|---|---|---|
| Semantic Auto | 0.813 → 0.863 (+0.050) | 0.865 → 0.862 (-0.003) | 0.325 → 0.280 (-0.045) |
| Contextual | 0.835 → **0.908** (+0.073) | 0.926 → **0.933** (+0.007) | 0.568 → 0.547 (-0.021) |
| HierarchicalPrepend | 0.836 → 0.876 (+0.040) | 0.904 → 0.902 (-0.002) | 0.552 → 0.554 (+0.002) |

- Qwen3에서 리랭커는 **Precision만 개선**하고, Recall은 거의 변화 없으며, **Relevancy는 오히려 하락하는 경향**이다
- bge-m3와 대조적: bge-m3는 리랭커 적용 시 세 지표 모두 개선되었으나, Qwen3는 Precision 외 효과가 미미하거나 역효과
- Qwen3 + Contextual + Reranker 조합이 Qwen3 내 최고 Precision(0.908)과 Recall(0.933)을 기록하나, Relevancy(0.547)는 Baseline(0.568)보다 하락
- Qwen3 벡터 검색의 노이즈가 많아 리랭커가 top-20에서 의미 있는 재정렬을 하기 어려운 것으로 해석된다

#### 3.3.6 이전 지표(참고용) 대비 분석

이전에 키워드 매칭 + 커스텀 LLM 판정으로 측정한 결과와 비교:

| 지표 체계 | 측정 결과 요약 |
|---|---|
| 키워드 매칭 (이전) | Hit Rate 0.60, Precision 0.20 → **과소평가 경향** |
| 커스텀 LLM 판정 (이전) | Hit Rate 0.87, Precision 0.38 → 개선되었으나 단순 yes/no |
| **DeepEval (현재)** | **C.Precision 0.88~0.93, C.Recall 0.91~0.93** → **문장 단위 세밀한 평가** |

DeepEval의 RAGAS 방법론은 단순 이진 판정이 아닌 문장 단위 분석으로, 더 정확하고 재현 가능한 평가를 제공한다.

### 3.4 리트리버 품질 소결

- **최고 종합 성능**: bge-m3 + HierarchicalPrepend + Reranker (C.Precision 0.926, C.Recall 0.933, C.Relevancy 0.606)
- **최고 Recall**: bge-m3 + Contextual + Baseline (0.934) — Recall 최우선 시 이 조합이 유리
- **bge-m3가 Qwen3를 모든 지표에서 상회** — 6건 평균 Precision +0.045, Recall +0.024, Relevancy +0.121
- 리랭커는 bge-m3에서 세 지표 모두 개선하나, Qwen3에서는 Precision만 개선하고 Relevancy는 역효과
- Relevancy는 bge-m3 기준 0.58~0.61 수준으로, top-5 중 약 3개가 관련 → 추가 개선 여지 존재

---

## 4. 대화 품질 평가

> **이 섹션은 backend 팀에서 작성 예정입니다.**

### 4.1 실험 설계

#### 4.1.1 평가 대상
- 응답 모델: ExaOne (RunPod Serverless)
- 입력: 리트리버 검색 context + 사용자 질문
- 출력: LLM 생성 응답

#### 4.1.2 평가 지표 (예시)

| 지표 | 설명 |
|---|---|
| Faithfulness | 응답이 제공된 context에 근거하는가 (환각 여부) |
| Answer Relevancy | 응답이 질문에 적절히 답하는가 |
| Hallucination Rate | context에 없는 정보를 생성하는 비율 |
| Response Latency | 응답 생성 소요 시간 |

### 4.2 실험 결과

(backend 팀 작성 예정)

### 4.3 분석

(backend 팀 작성 예정)

---

## 5. 보고서 품질 평가

> **이 섹션은 backend 팀에서 작성 예정입니다.**

### 5.1 실험 설계

#### 5.1.1 평가 대상
- 저장된 콘텐츠 기반으로 사용자 목적에 맞게 생성된 보고서
- 보고서 형식: 요약, 비교 분석, 트렌드 정리 등

#### 5.1.2 평가 지표 (예시)

| 지표 | 설명 |
|---|---|
| 목적 적합성 | 사용자의 보고서 생성 목적에 부합하는가 |
| 정보 완전성 | 저장된 콘텐츠의 핵심 정보를 빠짐없이 포함하는가 |
| 구조 품질 | 보고서 형식과 가독성이 적절한가 |
| 사실 정확성 | 저장된 원본 콘텐츠와 일치하는가 |

### 5.2 실험 결과

(backend 팀 작성 예정)

### 5.3 분석

(backend 팀 작성 예정)

---

## 6. 결론

### 6.1 최종 결과 요약 (12/12 실험 완료)

| 구성 | C.Precision | C.Recall | C.Relevancy | 비고 |
|---|---|---|---|---|
| bge-m3 + Semantic Auto (Baseline) | 0.882 | 0.909 | 0.581 | |
| bge-m3 + Contextual (Baseline) | 0.889 | **0.934** | 0.587 | 최고 Recall |
| bge-m3 + HierarchicalPrepend (Baseline) | 0.889 | 0.897 | 0.584 | |
| bge-m3 + Semantic Auto (Reranker) | 0.919 | 0.933 | 0.598 | |
| bge-m3 + Contextual (Reranker) | 0.894 | 0.933 | 0.593 | |
| **bge-m3 + HierarchicalPrepend (Reranker)** | **0.926** | **0.933** | **0.606** | **최고 종합 성능** |
| Qwen3 + Semantic Auto (Baseline) | 0.813 | 0.865 | 0.325 | |
| Qwen3 + Contextual (Baseline) | 0.835 | 0.926 | 0.568 | |
| Qwen3 + HierarchicalPrepend (Baseline) | 0.836 | 0.904 | 0.552 | |
| Qwen3 + Semantic Auto (Reranker) | 0.863 | 0.862 | 0.280 | Relevancy 최저 |
| Qwen3 + Contextual (Reranker) | 0.908 | 0.933 | 0.547 | Qwen3 내 최고 Precision |
| Qwen3 + HierarchicalPrepend (Reranker) | 0.876 | 0.902 | 0.554 | |

### 6.2 최종 권장 구성

| 항목 | 권장 | 근거 |
|---|---|---|
| 임베딩 모델 | **BAAI/bge-m3** | 모든 지표에서 Qwen3 상회 (6건 평균 P+0.045, R+0.024, Rel+0.121) |
| 청킹 전략 | **HierarchicalPrepend** (리랭커 병용 시) 또는 **Contextual** (Recall 최우선 시) | HierarchicalPrepend+Reranker 최고 종합, Contextual Baseline 최고 Recall |
| 리랭커 | **bge-reranker-v2-m3** | bge-m3 기준 Precision +0.037, Recall +0.036 개선 (HierarchicalPrepend 기준) |
| DeepEval 평가 모델 | gpt-4o-mini | 비용 효율적, 충분한 판정 정확도 |

### 6.3 향후 과제

1. 대화 품질 평가 (backend)
2. 보고서 품질 평가 (backend)
3. 최적 구성 프로덕션 적용

---

### 참고문헌

- Es, S., et al. (2023). "RAGAS: Automated Evaluation of Retrieval Augmented Generation." *arXiv:2309.15217*
- DeepEval Documentation: https://docs.confident-ai.com

---

*평가 도구: test/evaluation_ir.py | 프레임워크: DeepEval | 실험 추적: MLflow | 최종 수정: 2026-03-17*
