from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
import logging

logger = logging.getLogger(__name__)

def custom_api_exception_handler(exc, context):
    """
    Centralized intercept engine that converts standard DRF exceptions 
    and raw server breakdowns into a standardized, scannable JSON schema.
    """
    # Call DRF's default exception handler first to get the standard response
    response = exception_handler(exc, context)

    # If response is None, Django encountered an unhandled 500 Server Error
    if response is None:
        logger.error(f"Unhandled Server Exception: {str(exc)}", exc_info=True)
        return Response({
            "success": False,
            "error": {
                "code": "SERVER_ERROR",
                "message": "An unexpected error occurred on the server. Please try again later.",
                "details": str(exc) if hasattr(exc, 'args') else None
            }
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # Map status codes to clear, operational business error strings
    status_code_mappings = {
        400: "VALIDATION_ERROR",
        401: "UNAUTHORIZED_ACCESS",
        403: "ROLE_VIOLATION",
        404: "RESOURCE_NOT_FOUND",
        405: "METHOD_NOT_ALLOWED"
    }

    current_status = response.status_code
    error_code = status_code_mappings.get(current_status, "API_ERROR")

    # Re-structure the response data payload
    custom_response_data = {
        "success": False,
        "error": {
            "code": error_code,
            "message": response.data.get("detail", "Request failed validation constraints."),
            "details": response.data if "detail" not in response.data or len(response.data) > 1 else None
        }
    }

    # Clean up the detail duplicate out of details if it exists
    if custom_response_data["error"]["details"] and "detail" in custom_response_data["error"]["details"]:
        if len(custom_response_data["error"]["details"]) == 1:
            custom_response_data["error"]["details"] = None

    response.data = custom_response_data
    return response