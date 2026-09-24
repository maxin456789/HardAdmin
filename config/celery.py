import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('HardAdmin')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# задачи раз в час и раз в сутки
app.conf.beat_schedule = {
    'sla-check-new': {
        'task': 'HardAdmin.tasks.sla_check_unaccepted',
        'schedule': 3600,  # раз в час
    },
    'remind-stale': {
        'task': 'HardAdmin.tasks.remind_stale_tickets',
        'schedule': 86400,  # раз в сутки
    },
}