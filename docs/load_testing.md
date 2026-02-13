# Load Testing Guide

## 1) Install

```powershell
python -m pip install -r requirements-loadtest.txt
```

## 2) Bootstrap test user

```powershell
python manage.py bootstrap_loadtest --password "pass1234" --create-token
```

- 기본 사용자명: `loadtest-pro`
- 기본 플랜: `pro`
- 기본 인덱스 종목(`KOSPI`, `KOSDAQ`, `SPX`, `IXIC`) 시드

## 3) Environment variables

```powershell
$env:LOCUST_HOST = "http://localhost:8080"
$env:LOCUST_USERNAME = "loadtest-pro"
$env:LOCUST_PASSWORD = "pass1234"
$env:LOCUST_STOCK_SYMBOLS = "KOSPI,KOSDAQ,SPX,IXIC"
```

토큰을 이미 갖고 있으면 사용자명/비밀번호 대신:

```powershell
$env:LOCUST_API_TOKEN = "<TOKEN_VALUE>"
```

## 4) Run Locust (UI mode)

```powershell
locust -f loadtest/locustfile.py
```

- 브라우저에서 `http://localhost:8089` 접속
- 예시: `Users=30`, `Spawn rate=5`

## 5) Run Locust (headless mode)

```powershell
locust -f loadtest/locustfile.py --headless --users 30 --spawn-rate 5 --run-time 3m --csv loadtest/result
```

생성 파일:
- `loadtest/result_stats.csv`
- `loadtest/result_failures.csv`
- `loadtest/result_exceptions.csv`

## 6) Run baseline threshold check

```powershell
python scripts/run_loadtest_smoke.py --users 30 --spawn-rate 5 --run-time 2m --csv-prefix loadtest/result-smoke
```

기본 임계치:
- 실패율(`failure_ratio`) ≤ `2%`
- 평균 응답시간(`avg`) ≤ `800ms`
- p95 응답시간(`p95`) ≤ `1500ms`

임계치/실행값 환경변수:
- `LOADTEST_USERS` (기본 `30`)
- `LOADTEST_SPAWN_RATE` (기본 `5`)
- `LOADTEST_RUN_TIME` (기본 `2m`)
- `LOADTEST_MAX_FAILURE_RATIO` (기본 `0.02`)
- `LOADTEST_MAX_AVG_MS` (기본 `800`)
- `LOADTEST_MAX_P95_MS` (기본 `1500`)

이미 생성된 CSV만 검증하려면:

```powershell
python scripts/run_loadtest_smoke.py --skip-locust --csv-prefix loadtest/result
```

