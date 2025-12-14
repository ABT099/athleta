"""
FastAPI application entry point.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api import athletes, workouts, periodization, ml, prescriptions, plan_analyzer

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

# Include API routers
app.include_router(athletes.router, prefix="/api", tags=["athletes"])
app.include_router(workouts.router, prefix="/api", tags=["workouts"])
app.include_router(periodization.router, prefix="/api", tags=["periodization"])
app.include_router(ml.router, prefix="/api", tags=["ml"])
app.include_router(prescriptions.router, prefix="/api", tags=["prescriptions"])
app.include_router(plan_analyzer.router, tags=["plan-analyzer"])


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


