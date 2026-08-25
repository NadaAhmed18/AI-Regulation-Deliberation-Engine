from enum import Enum

class ScrapeStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
