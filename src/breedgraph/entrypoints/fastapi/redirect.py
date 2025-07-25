from fastapi import APIRouter
from fastapi.responses import RedirectResponse
from src.breedgraph.config import PROTOCOL, HOST_ADDRESS, VUE_PORT
router = APIRouter()

@router.get('/')
def read_root():
    return RedirectResponse(url=f"{PROTOCOL}://{HOST_ADDRESS}:{VUE_PORT}")
