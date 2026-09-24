import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse
from HardAdmin.models import Department, Employee, AssetType, Asset, Ticket
from HardAdmin.forms import TicketForm


@pytest.fixture(autouse=True)
def celery_eager(settings):
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.TASK_ALWAYS_EAGER = True


def create_employee(username, helpdesk=False):
    # создаёт пользователя и сотрудника
    user = User.objects.create_user(
        username=username, password='123', email=f'{username}@test.ru'
    )
    return Employee.objects.create(
        user=user,
        last_name=username.capitalize(),
        first_name='Тест',
        is_helpdesk_member=helpdesk,
    )



# МОДЕЛИ

@pytest.mark.django_db
def test_employee_full_name():
    emp = create_employee('ivanov')
    assert emp.full_name == 'Ivanov Тест'


@pytest.mark.django_db
def test_asset_str():
    asset_type = AssetType.objects.create(name='Ноутбук')
    asset = Asset.objects.create(
        inventory_number='INV-1', asset_type=asset_type, name='Dell'
    )
    assert str(asset) == 'INV-1 — Dell'


@pytest.mark.django_db
def test_ticket_crud():
    emp = create_employee('ivanov')
    # создание
    ticket = Ticket.objects.create(
        requester=emp, ticket_type='issue',
        subject='Сломался ПК', description='Не включается',
    )
    assert ticket.status == 'new'
    # чтение
    assert Ticket.objects.get(pk=ticket.pk).subject == 'Сломался ПК'
    # обновление
    ticket.status = 'in_progress'
    ticket.save()
    assert Ticket.objects.get(pk=ticket.pk).status == 'in_progress'
    # удаление
    ticket.delete()
    assert Ticket.objects.filter(pk=ticket.pk).count() == 0



# ФОРМЫ

@pytest.mark.django_db
def test_ticket_form_shows_only_own_assets():
    emp = create_employee('ivanov')
    asset_type = AssetType.objects.create(name='Монитор')
    own = Asset.objects.create(
        inventory_number='INV-2', asset_type=asset_type,
        status='in_use', assigned_to=emp,
    )
    foreign = Asset.objects.create(
        inventory_number='INV-3', asset_type=asset_type, status='in_use',
    )
    form = TicketForm(employee=emp)
    assert own in form.fields['asset'].queryset
    assert foreign not in form.fields['asset'].queryset



# ПРЕДСТАВЛЕНИЯ

@pytest.mark.django_db
def test_ticket_list_requires_login():
    client = Client()
    response = client.get(reverse('ticket_list'))
    assert response.status_code == 302  # редирект на страницу входа


@pytest.mark.django_db
def test_user_sees_only_own_tickets():
    emp1 = create_employee('ivanov')
    emp2 = create_employee('petrov')
    Ticket.objects.create(
        requester=emp1, ticket_type='issue', subject='Моя', description='test'
    )
    Ticket.objects.create(
        requester=emp2, ticket_type='issue', subject='Чужая', description='test'
    )
    client = Client()
    client.force_login(emp1.user)
    response = client.get(reverse('ticket_list'))
    subjects = [t.subject for t in response.context['tickets']]
    assert subjects == ['Моя']


@pytest.mark.django_db
def test_helpdesk_page_only_for_helpdesk():
    emp = create_employee('ivanov')
    client = Client()
    client.force_login(emp.user)
    response = client.get(reverse('helpdesk_list'))
    assert response.status_code == 302


@pytest.mark.django_db
def test_create_ticket():
    emp = create_employee('ivanov')
    client = Client()
    client.force_login(emp.user)
    response = client.post(reverse('ticket_create'), {
        'ticket_type': 'checkout',
        'priority': 'medium',
        'subject': 'Нужен монитор',
        'description': 'Для работы',
    })
    assert response.status_code == 302
    ticket = Ticket.objects.get(subject='Нужен монитор')
    assert ticket.requester == emp
    assert ticket.status == 'new'


@pytest.mark.django_db
def test_resolve_closes_ticket_and_breaks_asset():
    emp = create_employee('ivanov')
    helpdesk = create_employee('petrov', helpdesk=True)
    asset_type = AssetType.objects.create(name='Монитор')
    asset = Asset.objects.create(
        inventory_number='INV-4', asset_type=asset_type,
        status='in_use', assigned_to=emp,
    )
    ticket = Ticket.objects.create(
        requester=emp, ticket_type='issue', subject='Мигает экран',
        description='test', asset=asset,
        status='in_progress', assignee=helpdesk,
    )
    client = Client()
    client.force_login(helpdesk.user)
    response = client.post(
        reverse('ticket_resolve', kwargs={'pk': ticket.pk}),
        {'result': 'Матрица мертва, ремонт невозможен'},
    )
    assert response.status_code == 302
    ticket.refresh_from_db()
    asset.refresh_from_db()
    assert ticket.status == 'closed'
    assert asset.status == 'broken'      # без флага работоспособности
    assert asset.assigned_to is None     # вернулось на склад