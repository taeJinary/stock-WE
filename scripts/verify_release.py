import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
BANDIT_TARGETS = [
    "apps/api",
    "apps/accounts",
    "apps/briefing",
    "apps/dashboard",
    "apps/stocks",
    "apps/watchlist",
    "config",
    "crawler",
    "services",
]
BANDIT_EXCLUDES = [
    "apps/api/migrations",
    "apps/api/tests",
    "apps/accounts/migrations",
    "apps/accounts/tests",
    "apps/briefing/migrations",
    "apps/briefing/tests",
    "apps/dashboard/migrations",
    "apps/dashboard/tests",
    "apps/stocks/migrations",
    "apps/stocks/tests",
    "apps/watchlist/migrations",
    "apps/watchlist/tests",
]


def _build_env(base: dict[str, str], overrides: dict[str, str]) -> dict[str, str]:
    env = dict(base)
    env.update(overrides)
    return env


def _run_step(title: str, command: list[str], env: dict[str, str]) -> None:
    print(f"\n[STEP] {title}")
    print(" ".join(command))
    subprocess.run(command, cwd=ROOT, env=env, check=True)


def main() -> int:
    python = sys.executable
    base_env = os.environ.copy()
    shared_defaults = {
        "SECRET_KEY": base_env.get(
            "SECRET_KEY",
            "dev-secret-key-with-more-than-fifty-characters-1234567890",
        ),
        "REDIS_URL": base_env.get("REDIS_URL", "redis://localhost:6379/0"),
        "GEMINI_API_KEY": base_env.get("GEMINI_API_KEY", "test-gemini"),
        "ALPHA_VANTAGE_API_KEY": base_env.get("ALPHA_VANTAGE_API_KEY", "test-alpha"),
    }

    test_env = _build_env(
        base_env,
        {
            **shared_defaults,
            "DEBUG": base_env.get("DEBUG", "True"),
            "DJANGO_ENV": base_env.get("DJANGO_ENV", "development"),
        },
    )
    deploy_env = _build_env(
        base_env,
        {
            **shared_defaults,
            "DJANGO_ENV": "production",
            "DEBUG": "False",
            "ALLOWED_HOSTS": base_env.get("ALLOWED_HOSTS", "stock-we.example.com"),
            "ADMIN_URL_PATH": base_env.get("ADMIN_URL_PATH", "secure-admin/"),
            "CSRF_TRUSTED_ORIGINS": base_env.get(
                "CSRF_TRUSTED_ORIGINS",
                "https://stock-we.example.com",
            ),
            "SECURE_SSL_REDIRECT": "True",
            "SECURE_HSTS_SECONDS": "31536000",
            "SECURE_HSTS_INCLUDE_SUBDOMAINS": "True",
            "SECURE_HSTS_PRELOAD": "True",
            "SESSION_COOKIE_SECURE": "True",
            "CSRF_COOKIE_SECURE": "True",
        },
    )

    try:
        _run_step(
            "Django tests",
            [python, "manage.py", "test"],
            test_env,
        )
        _run_step(
            "Django deploy check",
            [python, "manage.py", "check", "--deploy"],
            deploy_env,
        )
        _run_step(
            "Bandit security scan",
            [
                python,
                "-m",
                "bandit",
                "-r",
                *BANDIT_TARGETS,
                "-x",
                ",".join(BANDIT_EXCLUDES),
            ],
            test_env,
        )
        _run_step(
            "Production preflight checks",
            [python, "scripts/verify_production_setup.py"],
            test_env,
        )
    except subprocess.CalledProcessError as exc:
        print(f"\n[FAIL] verification failed at exit code {exc.returncode}")
        return exc.returncode

    print("\n[OK] verification routine completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
