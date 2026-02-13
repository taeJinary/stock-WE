from __future__ import annotations

from django.test import SimpleTestCase

from scripts.verify_production_setup import (
    validate_caddy_text,
    validate_compose_text,
    validate_development_compose_text,
    validate_development_file,
    validate_production_files,
)


class VerifyProductionSetupTests(SimpleTestCase):
    def test_validate_development_file_passes_for_current_repository_files(self):
        errors = validate_development_file()
        self.assertEqual(errors, [])

    def test_validate_production_files_passes_for_current_repository_files(self):
        errors = validate_production_files()
        self.assertEqual(errors, [])

    def test_validate_compose_text_detects_port_exposure_and_missing_proxy_header(self):
        compose_text = """
services:
  proxy:
    image: caddy:2-alpine
    ports:
      - "${PROXY_HTTP_PORT:-80}:80"
      - "${PROXY_HTTPS_PORT:-443}:443"
  web:
    build: .
    ports:
      - "8080:8000"
  db:
    image: postgres:16
    ports:
      - "5432:5432"
  redis:
    image: redis:7
    ports:
      - "6379:6379"
"""

        errors = validate_compose_text(compose_text)

        self.assertIn("web service must not expose host ports in production compose.", errors)
        self.assertIn("db service must not expose host ports in production compose.", errors)
        self.assertIn("redis service must not expose host ports in production compose.", errors)
        self.assertIn("web service must define SECURE_PROXY_SSL_HEADER.", errors)
        self.assertIn("web service must set DJANGO_ENV: production.", errors)
        self.assertIn('web service must set DEBUG: "False".', errors)
        self.assertIn("web service command must include collectstatic before gunicorn.", errors)

    def test_validate_caddy_text_detects_missing_required_directives(self):
        caddy_text = """
localhost {
    reverse_proxy localhost:8000
}
"""

        errors = validate_caddy_text(caddy_text)

        self.assertIn("Caddyfile must use CADDY_SITE_ADDRESS for site binding.", errors)
        self.assertIn("Caddyfile must proxy traffic to web:8000.", errors)
        self.assertIn("Caddyfile must forward X-Forwarded-Proto header.", errors)

    def test_validate_development_compose_text_detects_missing_markers(self):
        compose_text = """
services:
  web:
    build: .
  db:
    image: postgres:16
  redis:
    image: redis:7
"""

        errors = validate_development_compose_text(compose_text)

        self.assertIn("web service must expose a host port in development compose.", errors)
        self.assertIn("web service must set DJANGO_ENV: development.", errors)
        self.assertIn('web service must set DEBUG: "True".', errors)
        self.assertIn("db service must expose host port in development compose.", errors)
        self.assertIn("redis service must expose host port in development compose.", errors)

