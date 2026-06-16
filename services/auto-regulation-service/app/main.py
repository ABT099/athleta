"""
FastAPI application entry point.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.config import settings
from app.modules.progression import router as workouts_router
from app.modules.prescription import router as prescriptions_router
from app.modules.periodization import router as periodization_router
from app.modules.injury import router as injury_router
from app.modules.ml.router import router as ml_router

logger = logging.getLogger(__name__)

# Create FastAPI application
app = FastAPI(
    title="AthleteAI - Progressive Overload Training System",
    description="AI-powered training system with intelligent progressive overload",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    # Check Celery/Redis connection
    try:
        from app.celery_app import celery_app
        # Ping Redis to verify connection
        celery_app.backend.client.ping()
        logger.info("✓ Celery/Redis connection established")
    except Exception as e:
        logger.warning(f"⚠ Celery/Redis not available: {e}. ML retraining will be disabled.")
    
    logger.info("✓ AthleteAI API started successfully")

# Include API routers
app.include_router(workouts_router, prefix="/api", tags=["workouts"])
app.include_router(periodization_router, prefix="/api", tags=["periodization"])
app.include_router(ml_router, prefix="/api", tags=["ml"])
app.include_router(prescriptions_router, prefix="/api", tags=["prescriptions"])
app.include_router(injury_router, prefix="/api", tags=["injury-prevention"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "AthleteAI Progressive Overload API",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


