
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List
class Settings(BaseSettings):
    SOURCE_TYPES:list
    MIN_DOCUMENTS:int



    model_config = SettingsConfigDict(env_file=".env")

def get_settings():
    return Settings()
