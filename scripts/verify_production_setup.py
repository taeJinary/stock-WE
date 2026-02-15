from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
COMPOSE_DEV_PATH = ROOT / "docker-compose.yml"
COMPOSE_PROD_PATH = ROOT / "docker-compose.prod.yml"
CADDYFILE_PATH = ROOT / "infra" / "caddy" / "Caddyfile"


def extract_service_blocks(compose_text: str) -> dict[str, list[str]]:
    blocks: dict[str, list[str]] = {}
    in_services = False
    current_service: str | None = None
    current_lines: list[str] = []

    for raw_line in compose_text.splitlines():
        line = raw_line.rstrip("\n")

        if not in_services:
            if line.strip() == "services:" and line.startswith("services:"):
                in_services = True
            continue

        if line and not line.startswith(" "):
            break

        is_service_header = (
            line.startswith("  ")
            and not line.startswith("    ")
            and line.strip().endswith(":")
        )
        if is_service_header:
            if current_service is not None:
                blocks[current_service] = current_lines
            current_service = line.strip()[:-1]
            current_lines = [line]
            continue

        if current_service is not None:
            current_lines.append(line)

    if current_service is not None:
        blocks[current_service] = current_lines

    return blocks


def _has_key(block_lines: list[str], key: str) -> bool:
    target = f"{key}:"
    return any(line.strip() == target for line in block_lines)


def _contains(block_lines: list[str], text: str) -> bool:
    return any(text in line for line in block_lines)


def _find_index(text: str, token: str) -> int:
    return text.find(token)


def validate_production_compose_text(compose_text: str) -> list[str]:
    errors: list[str] = []
    blocks = extract_service_blocks(compose_text)

    required_services = {"proxy", "web", "db", "redis"}
    missing = sorted(required_services - set(blocks.keys()))
    if missing:
        errors.append(f"Missing services in docker-compose.prod.yml: {', '.join(missing)}")
        return errors

    web_block = blocks["web"]
    db_block = blocks["db"]
    redis_block = blocks["redis"]
    proxy_block = blocks["proxy"]

    if _has_key(web_block, "ports"):
        errors.append("web service must not expose host ports in production compose.")
    if _has_key(db_block, "ports"):
        errors.append("db service must not expose host ports in production compose.")
    if _has_key(redis_block, "ports"):
        errors.append("redis service must not expose host ports in production compose.")

    if not _has_key(proxy_block, "ports"):
        errors.append("proxy service must expose ports for external traffic.")
    if not _contains(proxy_block, "PROXY_HTTP_PORT"):
        errors.append("proxy service must use PROXY_HTTP_PORT mapping.")
    if not _contains(proxy_block, "PROXY_HTTPS_PORT"):
        errors.append("proxy service must use PROXY_HTTPS_PORT mapping.")

    if not _contains(web_block, "SECURE_PROXY_SSL_HEADER"):
        errors.append("web service must define SECURE_PROXY_SSL_HEADER.")
    if not _contains(web_block, "DJANGO_ENV: production"):
        errors.append("web service must set DJANGO_ENV: production.")
    if not _contains(web_block, 'DEBUG: "False"'):
        errors.append('web service must set DEBUG: "False".')
    web_text = "\n".join(web_block)
    if "migrate" not in web_text:
        errors.append("web service command must include migrate before collectstatic in production compose.")
    if "collectstatic" not in web_text:
        errors.append("web service command must include collectstatic before gunicorn.")
    if "gunicorn" not in web_text:
        errors.append("web service command must include gunicorn in production compose.")
    migrate_index = _find_index(web_text, "migrate")
    collectstatic_index = _find_index(web_text, "collectstatic")
    gunicorn_index = _find_index(web_text, "gunicorn")
    if migrate_index != -1 and collectstatic_index != -1 and migrate_index > collectstatic_index:
        errors.append("web service command must run migrate before collectstatic in production compose.")
    if collectstatic_index != -1 and gunicorn_index != -1 and collectstatic_index > gunicorn_index:
        errors.append("web service command must include collectstatic before gunicorn.")

    return errors


def validate_development_compose_text(compose_text: str) -> list[str]:
    errors: list[str] = []
    blocks = extract_service_blocks(compose_text)

    required_services = {"web", "db", "redis"}
    missing = sorted(required_services - set(blocks.keys()))
    if missing:
        errors.append(f"Missing services in docker-compose.yml: {', '.join(missing)}")
        return errors

    web_block = blocks["web"]
    db_block = blocks["db"]
    redis_block = blocks["redis"]

    if not _has_key(web_block, "ports"):
        errors.append("web service must expose a host port in development compose.")
    if not _contains(web_block, "DJANGO_ENV: development"):
        errors.append("web service must set DJANGO_ENV: development.")
    if not _contains(web_block, 'DEBUG: "True"'):
        errors.append('web service must set DEBUG: "True".')
    web_text = "\n".join(web_block)
    if "migrate" not in web_text:
        errors.append("web service command must include migrate before runserver in development compose.")
    if "runserver" not in web_text:
        errors.append("web service command must include runserver in development compose.")
    migrate_index = _find_index(web_text, "migrate")
    runserver_index = _find_index(web_text, "runserver")
    if migrate_index != -1 and runserver_index != -1 and migrate_index > runserver_index:
        errors.append("web service command must run migrate before runserver in development compose.")

    if not _has_key(db_block, "ports"):
        errors.append("db service must expose host port in development compose.")
    if not _contains(db_block, "5432:5432"):
        errors.append('db service must map "5432:5432" in development compose.')

    if not _has_key(redis_block, "ports"):
        errors.append("redis service must expose host port in development compose.")
    if not _contains(redis_block, "6379:6379"):
        errors.append('redis service must map "6379:6379" in development compose.')

    return errors


def validate_caddy_text(caddy_text: str) -> list[str]:
    errors: list[str] = []
    if "CADDY_SITE_ADDRESS" not in caddy_text:
        errors.append("Caddyfile must use CADDY_SITE_ADDRESS for site binding.")
    if "reverse_proxy web:8000" not in caddy_text:
        errors.append("Caddyfile must proxy traffic to web:8000.")
    if "header_up X-Forwarded-Proto {scheme}" not in caddy_text:
        errors.append("Caddyfile must forward X-Forwarded-Proto header.")
    return errors


def validate_compose_text(compose_text: str) -> list[str]:
    # Backward compatible alias for tests and old imports.
    return validate_production_compose_text(compose_text)


def validate_production_files(
    compose_path: Path = COMPOSE_PROD_PATH,
    caddy_path: Path = CADDYFILE_PATH,
) -> list[str]:
    errors: list[str] = []

    if not compose_path.exists():
        return [f"Missing file: {compose_path}"]
    if not caddy_path.exists():
        return [f"Missing file: {caddy_path}"]

    compose_text = compose_path.read_text(encoding="utf-8")
    caddy_text = caddy_path.read_text(encoding="utf-8")

    errors.extend(validate_production_compose_text(compose_text))
    errors.extend(validate_caddy_text(caddy_text))
    return errors


def validate_development_file(compose_path: Path = COMPOSE_DEV_PATH) -> list[str]:
    if not compose_path.exists():
        return [f"Missing file: {compose_path}"]
    compose_text = compose_path.read_text(encoding="utf-8")
    return validate_development_compose_text(compose_text)


def main() -> int:
    errors = []
    errors.extend(validate_development_file())
    errors.extend(validate_production_files())
    if errors:
        print("[FAIL] production preflight checks failed")
        for error in errors:
            print(f"- {error}")
        return 1

    print("[OK] production preflight checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

