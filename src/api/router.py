# src/api/router.py
from fastapi import APIRouter
from config import settings

router = APIRouter(prefix=settings.API_V1_STR)