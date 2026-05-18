"""
FastAPI application initialization and middleware configuration.

This module sets up the main FastAPI app, enables CORS for frontend communication,
and registers API route handlers.

Architecture:
- CORS allows all origins (update for production to specific domain)
- Routes are namespaced under /api prefix
- Background processing handles long-running tasks asynchronously
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes.leads import router as leads_router

app = FastAPI(
    title="AI Growth Audit API",
    description="Lead intake and AI analysis platform",
    version="1.0.0"
)

# Enable CORS for frontend communication
# WARNING: In production, restrict to specific domain
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Update to ["https://yourdomain.com"] for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routes
app.include_router(leads_router, prefix="/api")


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"message": "Backend running successfully"}