from decouple import config
from pydantic import BaseModel

DEBUG = config("DEBUG", cast=bool, default=False)
DATABASE_URL = config("DATABASE_URL")

MEILI_URL = config("MEILI_URL")
MEILI_API_KEY = config("MEILI_API_KEY", default=None)
MEILI_SYNC_ON_START = config("MEILI_SYNC_ON_START", cast=bool, default=False)
MEILI_INDEX_NAME = config("MEILI_INDEX_NAME", default="msds")

S3_URL = config("S3_URL", default=None)
S3_ACCESS_KEY = config("S3_ACCESS_KEY")
S3_SECRET_KEY = config("S3_SECRET_KEY")
S3_BUCKET_NAME = config("S3_BUCKET_NAME", default="msds")


class LogConfig(BaseModel):
    """Logging configuration for the application."""

    LOGGER_NAME: str = "silicon"
    LOG_FORMAT: str = "%(levelprefix)s | %(asctime)s | %(message)s"
    LOG_LEVEL: str = "DEBUG"

    # Logging config
    version = 1
    disable_existing_loggers = False
    formatters = {
        "default": {
            "()": "uvicorn.logging.DefaultFormatter",
            "fmt": LOG_FORMAT,
            "datefmt": r"%Y-%m-%d %H:%M:%S",
        },
    }
    handlers = {
        "default": {
            "formatter": "default",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stderr",
        },
    }
    loggers = {
        LOGGER_NAME: {"handlers": ["default"], "level": LOG_LEVEL},
    }
