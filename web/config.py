"""Server configuration."""

import os

DATABASE_URL = os.environ.get("ALARM_WEB_DATABASE_URL", "sqlite:///alarm_viewer_server.db")
BLOB_STORAGE_PATH = os.environ.get("ALARM_WEB_BLOB_PATH", "./blobs")
SECRET_KEY = os.environ.get("ALARM_WEB_SECRET_KEY", "dev-secret-change-me")
CORS_ORIGINS = os.environ.get("ALARM_WEB_CORS_ALLOWED_ORIGINS", "*").split(",")
