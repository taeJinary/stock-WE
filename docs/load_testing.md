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

