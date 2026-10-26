import json
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from ariadne import graphql, combine_multipart_data
from graphql import GraphQLError, ValidationRule
from graphql.language import FieldNode, OperationDefinitionNode

from typing import Optional, Dict, Any

from breedgraph.domain.model.accounts import AccountStored
from breedgraph.custom_exceptions import UnauthorisedOperationError
from breedgraph.config import GQL_API_PATH, ENVIRONMENT, Environment, cookie_name

# logging
import logging
from breedgraph.entrypoints.fastapi.graphql.resolvers.queries.context_loaders import close_context
from breedgraph.entrypoints.fastapi.graphql.acceptances import terms_accepted
from breedgraph.entrypoints.fastapi.graphql.query_limits import QueryLimits

logger = logging.getLogger(__name__)

router = APIRouter()

# Debug errors carry a stack trace and the local variables of the raising frame, so only in development
GRAPHQL_DEBUG = ENVIRONMENT is Environment.DEVELOPMENT

# What may be asked before the Terms of Use are accepted: reading and accepting them, reading the privacy notice, and
# introspection
TERMS_FREE_FIELDS = frozenset({'termsOfUse', 'termsAccept', 'privacyNotice', '__schema', '__type', '__typename'})
TERMS_NOT_ACCEPTED = 'TERMS_NOT_ACCEPTED'


class TermsOfUseRequired(ValidationRule):
    """
    Refuses an operation asking for anything but the Terms of Use and the privacy notice, for a request whose user
    hasn't accepted the current Terms (docs/licences.md §4). Everyone accepts them first, through the website or the API.
    """
    def enter_operation_definition(self, node: OperationDefinitionNode, *_args):
        if any(
            not (isinstance(selection, FieldNode) and selection.name.value in TERMS_FREE_FIELDS)
            for selection in node.selection_set.selections
        ):
            self.report_error(GraphQLError(
                "Accept the Terms of Use first: read them with termsOfUse, and accept them with termsAccept",
                node,
                extensions={'code': TERMS_NOT_ACCEPTED}
            ))


def validation_rules(context, _document, _data):
    return [QueryLimits] if terms_accepted(context) else [QueryLimits, TermsOfUseRequired]


async def get_user_id(request: Request) -> Optional[AccountStored]:
    """Extract and validate user from auth token cookie"""
    token = request.cookies.get(cookie_name('auth_token'))
    logger.debug(f"GraphQL context builder - auth_token cookie {'present' if token else 'absent'}")
    if token is not None:
        try:
            auth_service = request.app.bus.auth_service
            user_id = auth_service.validate_login_token(token)
        except UnauthorisedOperationError as e:
            return None
        # Login tokens cannot be revoked, so check the account has not been deleted
        async with request.app.bus.views_factory.get_views(user_id=user_id) as views:
            if await views.accounts.user_exists():
                return user_id

    return None


async def get_context_value(request: Request):
    """Build GraphQL context with request, bus, auth service, and cookies to set"""
    context = {
        "request": request,
        "bus": request.app.bus,
        "auth_service": request.app.bus.auth_service,
        "brute_force_service": request.app.brute_force_service,
        "geocoding_service": request.app.geocoding_service,
        "user_id": await get_user_id(request),
        "cached_uow": None,
        "cookies_to_set": [],  # List to store cookies that should be set
        # the published Terms of Use and privacy notice, and what the user has accepted (graphql/acceptances.py), read
        # when first needed
        "terms_of_use": request.app.terms_of_use,
        "privacy_notice": request.app.privacy_notice,
        "acceptance_tokens": request.app.acceptance_tokens,
        "acceptances": None
    }
    logger.debug(f"GraphQL context builder - user {context['user_id']}")
    return context


async def extract_graphql_data(request: Request) -> Dict[str, Any]:
    """Extract GraphQL query data from request, similar to Ariadne's approach"""
    content_type = request.headers.get("content-type", "")

    if "application/json" in content_type:
        # Standard JSON GraphQL request
        return await request.json()
    elif "multipart/form-data" in content_type:
        # Get the form data from FastAPI/Starlette
        form = await request.form()

        # operations and map are sent as strings in the form
        operations = json.loads(form.get("operations"))
        map_data = json.loads(form.get("map"))

        # combine_multipart_data takes operations, map, and the files
        # It puts the file objects into the 'operations' variables dict
        return combine_multipart_data(
            operations,
            map_data,
            form  # Pass the form object containing files
        )
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
    logger.debug("GraphQL endpoint started")
    context = None
    try:
        data = await extract_graphql_data(request)
        context = await get_context_value(request)
        success, result = await graphql(
            request.app.graphql_schema,
            data,
            context_value=context,
            debug=GRAPHQL_DEBUG,
            validation_rules=validation_rules,
        )
        # Asking before accepting the Terms of Use is not a malformed request, so it is answered as one that ran
        terms_refused = not success and all(
            (error.get('extensions') or {}).get('code') == TERMS_NOT_ACCEPTED for error in result.get('errors') or []
        )
        status_code = 200 if success or terms_refused else 400
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
        logger.debug(f"GraphQL endpoint complete")

        return json_response

    except Exception as e:
        logger.error(f"GraphQL endpoint error: {str(e)}")
        return JSONResponse(
            content={"errors": [{"message": "Internal server error"}]},
            status_code=500
        )

    finally:
        await close_context(context)
        logger.debug("GraphQL endpoint complete")