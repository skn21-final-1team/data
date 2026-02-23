# Data

## 실행 전 필수 사항

1. `.env` 파일 설정 (본인 환경에 맞게)

## 초기 세팅 (pull 이후)

```bash
# 의존성 설치
uv sync

# Playwright 브라우저 설치 (최초 1회만)
uv run playwright install chromium
```

## 서버 실행

```bash
uvicorn main:app --reload --port 8001
```

## ruff 린팅 및 포맷팅 확인

```bash
ruff check .
ruff format --check .
```

## API 문서

- Swagger UI: http://localhost:8001/docs
- ReDoc: http://localhost:8001/redoc
