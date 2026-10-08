from breedgraph.config import GQL_API_PATH, ANALYSIS_WORKER_AUTH_TOKEN
from tests.breedgraph.e2e.utils import with_auth


async def post_to_submit_analysis(client, token: str, analysis: dict):
    json = {
        "query": (
            " mutation ( $analysis: AnalysisInput! ) { "
            "  analysisSubmit( analysis: $analysis ) { "
            "    status, result, errors { name, message, path } "
            "  } "
            " } "
        ),
        "variables": {"analysis": analysis}
    }
    headers = with_auth(csrf_token=client.headers["X-CSRF-Token"], auth_token=token)
    return await client.post(GQL_API_PATH, json=json, headers=headers)


async def post_to_get_analysis_submission(client, token: str, analysis_id: str):
    json = {
        "query": (
            " query ( $id: ID! ) { "
            "  analysisSubmission( id: $id ) { "
            "    status, errors { name, message } "
            "    result { "
            "      id, status, name, analysisType, datasetIds "
            "      exclusions { unitIds, start, end } "
            "      config { "
            "        ... on DescriptiveStatisticsConfig { "
            "          terms { reference { type, conceptId }, transformations } "
            "          grouping { time { assignment } } "
            "          interactions { terms { type } } "
            "        } "
            "      } "
            "      result { ... on DescriptiveStatisticsResult { analysisId, terms { count } } } "
            "      errors { code, message, path, recordIds } "
            "      warnings { code, message, path, recordIds } "
            "    } "
            "  } "
            " } "
        ),
        "variables": {"id": analysis_id}
    }
    headers = with_auth(csrf_token=client.headers["X-CSRF-Token"], auth_token=token)
    return await client.post(GQL_API_PATH, json=json, headers=headers)


async def post_to_get_recent_analysis_submissions(client, token: str):
    json = {
        "query": (
            " query { "
            "  analysisRecentSubmissions { status, result, errors { name, message } } "
            " } "
        )
    }
    headers = with_auth(csrf_token=client.headers["X-CSRF-Token"], auth_token=token)
    return await client.post(GQL_API_PATH, json=json, headers=headers)


def worker_headers() -> dict:
    return {"Authorization": f"Bearer {ANALYSIS_WORKER_AUTH_TOKEN}"}


async def post_to_get_dataset_submission_id(client, token: str, submission_id: str):
    json = {
        "query": (
            " query ( $id: ID! ) { "
            "  datasetsSubmission( id: $id ) { "
            "    status, result { status, datasetId, errors }, errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {"id": submission_id}
    }
    headers = with_auth(csrf_token=client.headers["X-CSRF-Token"], auth_token=token)
    return await client.post(GQL_API_PATH, json=json, headers=headers)
