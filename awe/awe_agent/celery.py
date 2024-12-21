from celery import Celery
import os

app = Celery(
    'awe_tasks',
    broker=os.getenv("CELERY_BROKER_URL"),
    backend=os.getenv("CELERY_BACKEND_URL"),
    task_routes={
        "awe.awe_agent.tasks.llm_task.llm": {"queue": "llm"},
        "awe.awe_agent.tasks.sd_task.sd": {"queue": "sd"}
    })
