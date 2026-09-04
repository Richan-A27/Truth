from fastapi import APIRouter

from app.ml.model_registry import models_loaded

router = APIRouter()


@router.get("/health")
async def health():
    return {"status": "ok", "models_loaded": models_loaded()}
