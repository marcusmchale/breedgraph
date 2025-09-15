import json
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from ariadne import graphql

from pathlib import Path
from typing import Optional, Dict, Any

from src.breedgraph.domain.model.accounts import AccountStored
from src.breedgraph.custom_exceptions import UnauthorisedOperationError
from src.breedgraph.config import GQL_API_PATH

# logging
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


async def get_user_id(request: Request) -> Optional[AccountStored]:
    """Extract and validate user from auth token cookie"""
    token = request.cookies.get('auth_token')
    logger.debug(f"GraphQL context builder - auth_token cookie: {token}")
    if token is not None:
        try:
            auth_service = request.app.auth_service
            return auth_service.validate_login_token(token)
        except UnauthorisedOperationError as e:
            logger.debug(f"Token validation failed: {str(e)}")
            raise
    return None


async def get_context_value(request: Request):
    """Build GraphQL context with request, bus, auth service, and cookies to set"""
    token = request.cookies.get('auth_token')
    logger.debug(f"GraphQL context builder - auth_token cookie: {token}")
    user_id = await get_user_id(request)
    logger.debug(f"GraphQL context builder - user_id: {user_id}")
    context = {
        "request": request,
        "bus": request.app.bus,
        "auth_service": request.app.auth_service,
        "cookies_to_set": []  # List to store cookies that should be set
    }
    logger.debug(f"GraphQL context builder - final context: {context}")
    return context


async def extract_graphql_data(request: Request) -> Dict[str, Any]:
    """Extract GraphQL query data from request, similar to Ariadne's approach"""
    content_type = request.headers.get("content-type", "")

    if "application/json" in content_type:
        # Standard JSON GraphQL request
        return await request.json()
    elif "application/graphql" in content_type:
        # Raw GraphQL query
        body = await request.body()
        query = body.decode('utf-8')
        return {"query": query}
    elif "application/x-www-form-urlencoded" in content_type:
        # Form data (less common but possible)
        form_data = await request.form()
        return dict(form_data)
    else:
        # Default to treating as raw GraphQL
        body = await request.body()
        try:
            # Try to parse as JSON first
            return json.loads(body.decode('utf-8'))
        except json.JSONDecodeError:
            # If not JSON, treat as raw GraphQL query
            return {"query": body.decode('utf-8')}


@router.post(f"/{GQL_API_PATH}")
async def graphql_server(request: Request):
    """Handle GraphQL POST requests"""
    try:
        data = await extract_graphql_data(request)
        context = await get_context_value(request)

        success, result = await graphql(
            request.app.graphql_schema,
            data,
            context_value=context,
            debug=True,
        )

        status_code = 200 if success else 400

        # Create the response with the GraphQL result
        json_response = JSONResponse(content=result, status_code=status_code)
        # Set any cookies that were queued during GraphQL execution
        for cookie_data in context.get("cookies_to_set", []):
            # Extract the cookie name from the 'key' field WITHOUT removing it
            cookie_name = cookie_data.get("key")
            # Create a copy of the dict without the 'key' field
            cookie_params = {k: v for k, v in cookie_data.items() if k != "key"}
            json_response.set_cookie(cookie_name, **cookie_params)
            logger.debug(f"Set cookie: {cookie_name}")

        return json_response

    except Exception as e:
        logger.error(f"GraphQL endpoint error: {str(e)}")
        return JSONResponse(
            content={"errors": [{"message": "Internal server error"}]},
            status_code=500
        )
