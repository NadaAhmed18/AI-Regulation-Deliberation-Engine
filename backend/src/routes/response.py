from typing import Any, Optional
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse


def success_response(
    message: str,
    data: Optional[Any] = None,
    status_code: int = 200,
) -> JSONResponse:

    return JSONResponse(
        status_code=status_code,
        content={
            "success": True,
            "status_code": status_code,
            "message": message,
            "data": jsonable_encoder(data),
        },
    )


def fail_response(
    message: str,
    data: Optional[Any] = None,
    error: Optional[Any] = None,
    status_code: int = 400,
) -> JSONResponse:

    content: dict[str, Any] = {
        "success": False,
        "status_code": status_code,
        "message": message,
        "data": jsonable_encoder(data),
    }

    if error is not None:
        content["error"] = jsonable_encoder(str(error) if isinstance(error, Exception) else error)

    return JSONResponse(
        status_code=status_code,
        content=content,
    )