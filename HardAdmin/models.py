from django.db import models
from django.contrib.auth.models import User


# отделы компании
class Department(models.Model):
    name = models.CharField(max_length=100, verbose_name='Название отдела')
    location = models.CharField(max_length=200, blank=True, verbose_name='Локация')
    is_active = models.BooleanField(default=True, verbose_name='Отдел активен')

    class Meta:
        verbose_name = 'Отдел'
        verbose_name_plural = 'Отделы'
        ordering = ['name']

    def __str__(self):
        return self.name


# сотрудники: один к одному с пользователем Django
class Employee(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, verbose_name='Учётная запись'
    )

    last_name = models.CharField(max_length=100, verbose_name='Фамилия')
    first_name = models.CharField(max_length=50, verbose_name='Имя')
    middle_name = models.CharField(max_length=100, blank=True, verbose_name='Отчество')
    is_helpdesk_member = models.BooleanField(default=False, verbose_name='Сотрудник HelpDesk')
    position = models.CharField(max_length=100, blank=True, verbose_name='Должность')
    department = models.ForeignKey(
        Department, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name='Отдел', related_name='employees'
    )
    phone_internal = models.CharField(max_length=20, blank=True, verbose_name='Внутренний номер')
    phone_mobile = models.CharField(max_length=20, blank=True, verbose_name='Мобильный номер')
    is_employed = models.BooleanField(default=True, verbose_name='Работает')
    notes = models.TextField(blank=True, verbose_name='Примечания')

    class Meta:
        verbose_name = 'Сотрудник'
        verbose_name_plural = 'Сотрудники'
        ordering = ['last_name', 'first_name']

    @property
    def full_name(self):
        """Возвращает полное ФИО строкой."""
        if self.middle_name:
            return f'{self.last_name} {self.first_name} {self.middle_name}'
        return f'{self.last_name} {self.first_name}'

    def __str__(self):
        return self.full_name


# типы оборудования
class AssetType(models.Model):
    CATEGORY_CHOICES = [
        ('IT', 'IT-оборудование'),
        ('NETWORK', 'Сетевое оборудование'),
        ('PERIPHERY', 'Периферия'),
        ('PHONE', 'Телефония'),
    ]

    name = models.CharField(max_length=100, unique=True, verbose_name='Тип оборудования')
    category = models.CharField(
        max_length=20, choices=CATEGORY_CHOICES, default='IT',
        verbose_name='Категория'
    )

    class Meta:
        verbose_name = 'Тип оборудования'
        verbose_name_plural = 'Типы оборудования'
        ordering = ['name']

    def __str__(self):
        return self.name


# оборудование
class Asset(models.Model):
    STATUS_CHOICES = [
        ('storage', 'На складе'),
        ('in_use', 'В работе'),
        ('in_repair', 'В ремонте'),
        ('broken', 'Неисправен'),
        ('written_off', 'Списан'),
    ]

    inventory_number = models.CharField(
        max_length=100, unique=True, db_index=True,
        verbose_name='Инвентарный номер'
    )
    serial_number = models.CharField(
        max_length=100, blank=True, db_index=True,
        verbose_name='Серийный номер'
    )
    asset_type = models.ForeignKey(
        AssetType, on_delete=models.PROTECT,
        verbose_name='Тип оборудования', related_name='assets'
    )
    name = models.CharField(max_length=255, blank=True, verbose_name='Название')
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='storage',
        verbose_name='Статус'
    )
    assigned_to = models.ForeignKey(
        Employee, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name='Закреплено за', related_name='assets'
    )
    arrival_date = models.DateField(null=True, blank=True, verbose_name='Дата поступления')
    warranty_end_date = models.DateField(null=True, blank=True, verbose_name='Окончание гарантии')
    qr_code_id = models.CharField(
        max_length=100, unique=True, blank=True, null=True, default=None,
        verbose_name='ID штрихкода'
    )
    notes = models.TextField(blank=True, verbose_name='Примечания')

    class Meta:
        verbose_name = 'Оборудование'
        verbose_name_plural = 'Оборудование'
        ordering = ['inventory_number']

    def __str__(self):
        name_part = self.name or self.asset_type.name
        return f'{self.inventory_number} — {name_part}'


# заявки сотрудников
class Ticket(models.Model):
    TICKET_TYPE_CHOICES = [
        ('checkout', 'Выдача'),
        ('issue', 'Неисправность'),
        ('write_off', 'Списание'),
    ]

    PRIORITY_CHOICES = [
        ('low', 'Низкий'),
        ('medium', 'Средний'),
        ('high', 'Высокий'),
        ('critical', 'Критический'),
    ]

    STATUS_CHOICES = [
        ('new', 'Новая'),
        ('in_progress', 'В работе'),
        ('closed', 'Закрыта'),
    ]

    requester = models.ForeignKey(
        Employee, on_delete=models.PROTECT,
        verbose_name='Заявитель', related_name='requested_tickets'
    )
    ticket_type = models.CharField(
        max_length=20, choices=TICKET_TYPE_CHOICES,
        verbose_name='Тип заявки'
    )
    priority = models.CharField(
        max_length=20, choices=PRIORITY_CHOICES, default='medium',
        verbose_name='Приоритет'
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='new',
        verbose_name='Статус'
    )
    subject = models.CharField(max_length=255, verbose_name='Тема')
    description = models.TextField(verbose_name='Описание')
    asset = models.ForeignKey(
        Asset, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name='Оборудование', related_name='tickets'
    )
    assignee = models.ForeignKey(
        Employee, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name='Исполнитель', related_name='assigned_tickets'
    )
    result = models.TextField(blank=True, verbose_name='Результат решения')
    notes = models.TextField(blank=True, verbose_name='Заметки HelpDesk')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создана')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Обновлена')
    closed_at = models.DateTimeField(null=True, blank=True, verbose_name='Закрыта')

    class Meta:
        verbose_name = 'Заявка'
        verbose_name_plural = 'Заявки'
        ordering = ['-created_at']

    # цвет статуса для шаблонов
    def get_status_badge_class(self):
        return {
            'new': 'bg-primary',
            'in_progress': 'bg-success',
            'closed': 'bg-dark',
        }.get(self.status, 'bg-secondary')

    def __str__(self):
        return f'#{self.pk} — {self.get_ticket_type_display()}: {self.subject}'
