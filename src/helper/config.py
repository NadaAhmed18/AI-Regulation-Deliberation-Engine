
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List
class Settings(BaseSettings):
    SOURCE_TYPES:list
    MIN_DOCUMENTS:int
    APP_VERSION:str
    APP_NAME:str

    USER_AGENT:str
    REQUEST_DELAY_SECONDS:int
    REQUEST_TIMEOUT_SECONDS:int




    model_config = SettingsConfigDict(env_file=".env")

def get_settings():
    return Settings()
