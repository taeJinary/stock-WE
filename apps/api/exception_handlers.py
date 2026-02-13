from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

STATUS_CODE_TO_ERROR = {
    status.HTTP_400_BAD_REQUEST: "BAD_REQUEST",
    status.HTTP_401_UNAUTHORIZED: "UNAUTHORIZED",
    status.HTTP_403_FORBIDDEN: "FORBIDDEN",
    status.HTTP_404_NOT_FOUND: "NOT_FOUND",
    status.HTTP_405_METHOD_NOT_ALLOWED: "METHOD_NOT_ALLOWED",
    status.HTTP_429_TOO_MANY_REQUESTS: "RATE_LIMITED",
}


def _extract_error_message(payload):
    if isinstance(payload, dict):
        detail = payload.get("detail")
        if isinstance(detail, str) and detail:
            return detail
        for value in payload.values():
            if isinstance(value, list) and value:
                return str(value[0])
            if isinstance(value, str) and value:
                return value
        return "Request validation failed."

    if isinstance(payload, list) and payload:
        return str(payload[0])

    if isinstance(payload, str) and payload:
        return payload

    return "Request failed."


def _resolve_error_code(exc, http_status):
    if isinstance(exc, ValidationError):
        return "VALIDATION_ERROR"
    return STATUS_CODE_TO_ERROR.get(http_status, "API_ERROR")


def api_exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is None:
        return Response(
            {
                "status": "error",
                "code": "INTERNAL_ERROR",
                "message": "Internal server error.",
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    original_payload = response.data
    response.data = {
        "status": "error",
        "code": _resolve_error_code(exc, response.status_code),
        "message": _extract_error_message(original_payload),
    }
    if original_payload not in (None, "", {}, []):
        response.data["errors"] = original_payload
    return response
