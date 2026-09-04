import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes_health import router as health_router
from app.api.routes_verify import router as verify_router
from app.config import get_settings
from app.ml.model_registry import load_all

settings = get_settings()
logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Loading ML models...")
    load_all()
    logger.info("Models loaded.")
    yield


app = FastAPI(title="Truth Verification API", lifespan=lifespan)
app.include_router(health_router)
app.include_router(verify_router)
