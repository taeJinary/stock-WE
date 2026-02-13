import os
import random

from locust import HttpUser, between, task


def _parse_symbols(raw_value: str) -> list[str]:
    symbols = [item.strip().upper() for item in raw_value.split(",") if item.strip()]
    return symbols or ["KOSPI", "KOSDAQ", "SPX", "IXIC"]


class ApiLoadUser(HttpUser):
    wait_time = between(1.0, 3.0)
    host = os.getenv("LOCUST_HOST", "http://localhost:8080")

    def on_start(self):
        self.symbols = _parse_symbols(os.getenv("LOCUST_STOCK_SYMBOLS", "KOSPI,KOSDAQ,SPX,IXIC"))
        self.auth_headers = self._resolve_auth_headers()

    def _resolve_auth_headers(self) -> dict[str, str]:
        preset_token = os.getenv("LOCUST_API_TOKEN", "").strip()
        if preset_token:
            return {"Authorization": f"Token {preset_token}"}

        username = os.getenv("LOCUST_USERNAME", "").strip()
        password = os.getenv("LOCUST_PASSWORD", "")
        if not username or not password:
            raise RuntimeError(
                "LOCUST_API_TOKEN 또는 LOCUST_USERNAME/LOCUST_PASSWORD 환경변수를 설정해야 합니다."
            )

        payload = {"username": username, "password": password}
        with self.client.post(
            "/api/v1/auth/token/",
            json=payload,
            name="POST /api/v1/auth/token/",
            catch_response=True,
        ) as response:
            if response.status_code != 201:
                response.failure(f"token issue failed: {response.status_code}")
                raise RuntimeError("토큰 발급 실패")

            body = response.json()
            token = (body.get("data") or {}).get("token")
            if not token:
                response.failure("token missing in response")
                raise RuntimeError("응답에 토큰이 없습니다.")

            response.success()
            return {"Authorization": f"Token {token}"}

    def _authorized_get(self, path: str, *, name: str):
        with self.client.get(path, headers=self.auth_headers, name=name, catch_response=True) as response:
            if response.status_code != 200:
                response.failure(f"unexpected status: {response.status_code}")
                return
            response.success()

    @task(4)
    def market_summary(self):
        self._authorized_get("/api/v1/market/summary/", name="GET /api/v1/market/summary/")

    @task(3)
    def top_interest(self):
        self._authorized_get(
            "/api/v1/interest/top/?limit=10&hours=24",
            name="GET /api/v1/interest/top/",
        )

    @task(2)
    def interest_anomalies(self):
        self._authorized_get(
            "/api/v1/interest/anomalies/?limit=8&recent_hours=6&baseline_hours=72",
            name="GET /api/v1/interest/anomalies/",
        )

    @task(3)
    def stock_summary(self):
        symbol = random.choice(self.symbols)
        self._authorized_get(
            f"/api/v1/stocks/{symbol}/summary/?price_days=30&interest_days=60&news_limit=5",
            name="GET /api/v1/stocks/:symbol/summary/",
        )
