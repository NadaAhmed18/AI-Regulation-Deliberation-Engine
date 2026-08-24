from fastapi import APIRouter,Depends
from helper.config import get_settings 

data_router = APIRouter(
    prefix="Ai-Regulation-Qubeterra",
    tags=['api_v1','data']
)


