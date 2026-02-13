import os
import sys
from importlib.util import find_spec
from pathlib import Path
from typing import Any

from django.core.exceptions import ImproperlyConfigured

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if value:
        return value
    raise ImproperlyConfigured(f"Missing required environment variable: {name}")


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ImproperlyConfigured(f"{name} must be an integer") from exc


def _env_list(name: str, default: list[str] | None = None) -> list[str]:
    raw = os.getenv(name)
    if raw is None:
        return default or []
    return [item.strip() for item in raw.split(",") if item.strip()]


def _env_secure_proxy_header(name: str = "SECURE_PROXY_SSL_HEADER") -> tuple[str, str] | None:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return None

    parts = [item.strip() for item in raw.split(",", 1)]
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ImproperlyConfigured(f"{name} must be in HEADER_NAME,header_value format")

    return parts[0], parts[1]


def _module_exists(module_name: str) -> bool:
    return find_spec(module_name) is not None


def _build_database_config(database_url: str) -> dict[str, Any]:
    # Minimal parser with sqlite default for local bootstrap.
    if database_url.startswith("sqlite:///"):
        db_path = database_url.removeprefix("sqlite:///")
        return {"ENGINE": "django.db.backends.sqlite3", "NAME": db_path}

    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    if not database_url.startswith("postgresql://"):
        raise ImproperlyConfigured("DATABASE_URL must start with sqlite:/// or postgresql://")

    from urllib.parse import urlparse

    parsed = urlparse(database_url)
    if not parsed.path:
        raise ImproperlyConfigured("DATABASE_URL is missing database name")

    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": parsed.path.lstrip("/"),
        "USER": parsed.username or "",
        "PASSWORD": parsed.password or "",
        "HOST": parsed.hostname or "",
        "PORT": str(parsed.port or "5432"),
    }


_load_dotenv(BASE_DIR / ".env")

DJANGO_ENV = os.getenv("DJANGO_ENV", "development").strip().lower()
IS_PRODUCTION = DJANGO_ENV in {"production", "prod"}
IS_TESTING = len(sys.argv) > 1 and sys.argv[1] == "test"

DEBUG = _env_bool("DEBUG", default=not IS_PRODUCTION)
if IS_PRODUCTION and DEBUG:
    raise ImproperlyConfigured("DEBUG must be False when DJANGO_ENV is production")

SECRET_KEY = _require_env("SECRET_KEY")
if IS_PRODUCTION:
    is_placeholder = SECRET_KEY.startswith("replace-with-")
    if is_placeholder or len(SECRET_KEY) < 50 or len(set(SECRET_KEY)) < 5:
        raise ImproperlyConfigured("SECRET_KEY is too weak for production")

default_allowed_hosts = ["localhost", "127.0.0.1"] if DEBUG else []
ALLOWED_HOSTS = _env_list("ALLOWED_HOSTS", default=default_allowed_hosts)
if not DEBUG and not ALLOWED_HOSTS:
    raise ImproperlyConfigured("ALLOWED_HOSTS must be set when DEBUG is False")

CSRF_TRUSTED_ORIGINS = _env_list("CSRF_TRUSTED_ORIGINS", default=[])


INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "apps.api.apps.ApiConfig",
    "apps.accounts.apps.AccountsConfig",
    "apps.dashboard.apps.DashboardConfig",
    "apps.stocks.apps.StocksConfig",
    "apps.briefing.apps.BriefingConfig",
    "apps.watchlist.apps.WatchlistConfig",
]

if _module_exists("django_celery_beat"):
    INSTALLED_APPS.append("django_celery_beat")

REST_FRAMEWORK = {
    "EXCEPTION_HANDLER": "apps.api.exception_handlers.api_exception_handler",
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.ScopedRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "api_read": os.getenv("API_THROTTLE_RATE", "120/min"),
    },
}

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
]
if _module_exists("whitenoise") and not DEBUG:
    MIDDLEWARE.append("whitenoise.middleware.WhiteNoiseMiddleware")
MIDDLEWARE += [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'db.sqlite3'}")
DATABASES = {"default": _build_database_config(DATABASE_URL)}
DATABASES["default"]["CONN_MAX_AGE"] = _env_int("CONN_MAX_AGE", default=600)

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

AUTH_USER_MODEL = "accounts.User"

LANGUAGE_CODE = "ko-kr"

TIME_ZONE = "Asia/Seoul"

USE_I18N = True

USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
if _module_exists("whitenoise") and not DEBUG:
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
    }

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = _env_bool("SESSION_COOKIE_SECURE", default=not DEBUG)
CSRF_COOKIE_SECURE = _env_bool("CSRF_COOKIE_SECURE", default=not DEBUG)
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_SSL_REDIRECT = _env_bool("SECURE_SSL_REDIRECT", default=not DEBUG)
SECURE_HSTS_SECONDS = _env_int("SECURE_HSTS_SECONDS", default=0 if DEBUG else 31536000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = _env_bool(
    "SECURE_HSTS_INCLUDE_SUBDOMAINS",
    default=not DEBUG,
)
SECURE_HSTS_PRELOAD = _env_bool("SECURE_HSTS_PRELOAD", default=not DEBUG)
SECURE_REFERRER_POLICY = os.getenv("SECURE_REFERRER_POLICY", "same-origin")
SECURE_PROXY_SSL_HEADER = _env_secure_proxy_header()

REDIS_URL = _require_env("REDIS_URL")
if IS_TESTING:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "westock-test-cache",
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
        }
    }

CACHE_TTL_MARKET_SUMMARY = _env_int("CACHE_TTL_MARKET_SUMMARY", default=300)
CACHE_TTL_TOP_INTEREST = _env_int("CACHE_TTL_TOP_INTEREST", default=300)
CACHE_TTL_HEATMAP = _env_int("CACHE_TTL_HEATMAP", default=600)
CACHE_TTL_TIMELINE = _env_int("CACHE_TTL_TIMELINE", default=600)
CACHE_TTL_ANOMALIES = _env_int("CACHE_TTL_ANOMALIES", default=300)
CACHE_TTL_STOCK_DETAIL = _env_int("CACHE_TTL_STOCK_DETAIL", default=300)

CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
if _module_exists("celery"):
    from celery.schedules import crontab

    CELERY_BEAT_SCHEDULE = {
        "daily-data-pipeline": {
            "task": "apps.briefing.tasks.run_daily_pipeline_task",
            "schedule": crontab(hour=7, minute=0),
        }
    }

GEMINI_API_KEY = _require_env("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
ALPHA_VANTAGE_API_KEY = _require_env("ALPHA_VANTAGE_API_KEY")

EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend",
)
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "noreply@westock.local")

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "[%(asctime)s] %(levelname)s %(name)s: %(message)s",
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
        }
    },
    "root": {
        "handlers": ["console"],
        "level": LOG_LEVEL,
    },
    "loggers": {
        "httpx": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "httpcore": {"handlers": ["console"], "level": "WARNING", "propagate": False},
    },
}
