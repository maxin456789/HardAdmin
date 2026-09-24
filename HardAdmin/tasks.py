from celery import shared_task
from django.core.mail import send_mail
from django.utils import timezone
from datetime import timedelta
from django.conf import settings
from HardAdmin.models import Ticket, Employee


# письмо по событию с заявкой
@shared_task
def send_ticket_notification(ticket_id, event_type):
    ticket = Ticket.objects.select_related(
        'requester__user', 'assignee__user'
    ).get(pk=ticket_id)

    subject_map = {
        'created': f'[HardAdmin] Создана новая заявка #{ticket.pk}',
        'assigned': f'[HardAdmin] Заявка #{ticket.pk} принята в работу',
        'closed': f'[HardAdmin] Заявка #{ticket.pk} закрыта',
        'sla': f'[HardAdmin] SLA: заявка #{ticket.pk} не принята!',
    }
    subject = subject_map.get(
        event_type, f'[HardAdmin] Обновление по заявке #{ticket.pk}'
    )

    message = (
        f'Заявка: #{ticket.pk}\n'
        f'Тема: {ticket.subject}\n'
        f'Статус: {ticket.get_status_display()}\n'
        f'Заявитель: {ticket.requester.full_name}\n'
    )
    if ticket.assignee:
        message += f'Исполнитель: {ticket.assignee.full_name}\n'
    if ticket.asset:
        message += f'Оборудование: {ticket.asset}\n'

    # пишем заявителю и исполнителю
    recipients = []
    if ticket.requester and ticket.requester.user.email:
        recipients.append(ticket.requester.user.email)
    if ticket.assignee and ticket.assignee.user.email and ticket.assignee != ticket.requester:
        recipients.append(ticket.assignee.user.email)

    if recipients:
        send_mail(
            subject, message, settings.EMAIL_FROM,
            recipients, fail_silently=True
        )
    return f'Notification sent for ticket #{ticket_id} ({event_type})'


# напоминание: заявка две недели В РАБОТЕ
@shared_task
def remind_stale_tickets():
    now = timezone.now()
    tickets = Ticket.objects.filter(
        status='in_progress',
        updated_at__lte=now - timedelta(days=14),
        updated_at__gt=now - timedelta(days=15),
    ).select_related('assignee__user', 'requester')

    count = 0
    for ticket in tickets:
        if not ticket.assignee or not ticket.assignee.user.email:
            continue
        subject = f'[HardAdmin] Заявка #{ticket.pk} в работе 2 недели — проверьте'
        message = (
            f'Заявка #{ticket.pk} не обновлялась больше 2 недель.\n\n'
            f'Тема: {ticket.subject}\n'
            f'Заявитель: {ticket.requester.full_name}\n'
            f'Последнее обновление: {ticket.updated_at:%d.%m.%Y %H:%M}\n\n'
            f'Проверьте заявку: завершите её или оставьте комментарий.'
        )
        send_mail(
            subject, message, settings.EMAIL_FROM,
            [ticket.assignee.user.email], fail_silently=True
        )
        count += 1
    return f'Reminders sent: {count}'


# новую заявку никто не взял больше 2 часов
@shared_task
def sla_check_unaccepted():
    threshold = timezone.now() - timedelta(hours=2)
    tickets = Ticket.objects.filter(
        status='new',
        created_at__lt=threshold,
        assignee__isnull=True,
    )
    count = tickets.count()

    for ticket in tickets:
        helpdesk_emails = list(
            Employee.objects.filter(
                is_helpdesk_member=True,
                is_employed=True,
                user__email__isnull=False,
            ).exclude(user__email='').values_list('user__email', flat=True)
        )
        if helpdesk_emails:
            subject = f'[HardAdmin] SLA: заявка #{ticket.pk} не принята!'
            message = (
                f'Внимание! Заявка без исполнителя уже 2+ часа:\n\n'
                f'Заявка: #{ticket.pk}\n'
                f'Тема: {ticket.subject}\n'
                f'Заявитель: {ticket.requester.full_name}\n'
                f'Создана: {ticket.created_at:%d.%m.%Y %H:%M}\n'
                f'Приоритет: {ticket.get_priority_display()}\n\n'
                f'Срочно примите заявку в работу!'
            )
            send_mail(
                subject, message, settings.EMAIL_FROM,
                helpdesk_emails, fail_silently=True
            )
    return f'SLA check: {count} unaccepted tickets found'