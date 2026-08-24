from fastapi import APIRouter,Depends
from helper.config import get_settings 
base_router = APIRouter(
    prefix="Ai-Regulation-Qubeterra",
    tags=['api_v1','base']
)

@base_router.get("/Health")
async def welcome(app_settings=Depends(get_settings)):
    app_name= app_settings.APP_NAME
    version=app_settings.APP_VERSION
    
    return {"app_name": app_name,
            "app_version":version}