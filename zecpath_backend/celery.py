import os
from celery import Celery

# 🐛 FIXED: Changed setDefault to lowercase setdefault
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'zecpath_backend.settings')

app = Celery('zecpath_backend')

# Load configuration keys directly from settings.py using a CELERY_ namespace prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Automatically discover asynchronous @shared_task blocks inside all apps' tasks.py files.
app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')