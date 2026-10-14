from fastapi import APIRouter
from fastapi.responses import RedirectResponse
from breedgraph.config import get_vue_url
router = APIRouter()

@router.get('/')
def read_root():
    return RedirectResponse(url=get_vue_url())
