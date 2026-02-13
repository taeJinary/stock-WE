from rest_framework.response import Response


def success_response(data, *, meta=None, status_code=200):
    payload = {
        "status": "success",
        "data": data,
    }
    if meta is not None:
        payload["meta"] = meta
    return Response(payload, status=status_code)
