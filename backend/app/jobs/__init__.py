from celery import Celery
from app.config import settings

celery_app = Celery(
    