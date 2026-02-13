# stock-WE

## Verification

release 전 아래 루틴을 실행합니다.

```powershell
python scripts/verify_release.py
```

PowerShell wrapper:

```powershell
.\scripts\verify_release.ps1
```

## Production Compose

프로덕션 실행은 `docker-compose.prod.yml`을 사용합니다.

```powershell
docker compose -f docker-compose.prod.yml up -d --build
```

보안 정책:
- `db`, `redis`는 `ports`를 열지 않아 Docker 내부 네트워크에서만 접근합니다.
- `web`은 내부 네트워크에서만 열리고, 외부 노출은 `proxy`(`PROXY_HTTP_PORT`, `PROXY_HTTPS_PORT`)만 허용합니다.
- `DATABASE_URL`은 `POSTGRES_USER`/`POSTGRES_PASSWORD`/`POSTGRES_DB`로 조합되어 Postgres로 강제됩니다.
- `proxy`는 `infra/caddy/Caddyfile` 기준으로 HTTPS를 종단하고 `X-Forwarded-Proto` 헤더를 전달합니다.

프로덕션 필수 환경값 예시:
- `CADDY_SITE_ADDRESS=stock-we.example.com`
- `SECURE_PROXY_SSL_HEADER=HTTP_X_FORWARDED_PROTO,https`
