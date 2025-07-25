"""
API router for v1 endpoints.
"""
from fastapi import APIRouter

from app.api.v1.endpoints import health, email, stocks, prices

api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(email.router, prefix="/email", tags=["email"])
api_router.include_router(stocks.router, prefix="/stocks", tags=["stocks"])
api_router.include_router(prices.router, prefix="/prices", tags=["prices"])