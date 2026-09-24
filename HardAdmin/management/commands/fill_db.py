from django.core.management.base import BaseCommand
from faker import Faker
from django.contrib.auth.models import User
from HardAdmin.models import Department, Employee, AssetType, Asset, Ticket
import random
from datetime import timedelta

fake = Faker('ru_RU')


class Command(BaseCommand):
    help = 'Наполнение БД тестовыми данными'

    def handle(self, *args, **options):
        self.stdout.write('Создание отделов')
        dept_names = [
            'IT-отдел', 'Бухгалтерия', 'Служба эксплуатации', 'Отдел кадров',
            'Логистика', 'Склад', 'Служба безопасности'
        ]
        departments = []
        for name in dept_names:
            dept = Department.objects.create(
                name=name, location=fake.address(), is_active=True
            )
            departments.append(dept)

        self.stdout.write('Создание пользователей и сотрудников')
        positions = [
            'Инженер', 'Техник', 'Бухгалтер', 'Кадровик',
            'Кладовщик', 'Администратор', 'Руководитель'
        ]
        employees = []
        for i in range(40):
            username = f'user_{i:03d}'
            user = User.objects.create_user(
                username=username,
                email=f'{username}@test.local',
                password='123456'
            )
            last_name = fake.last_name()
            first_name = fake.first_name()
            middle_name = fake.middle_name() if random.random() > 0.3 else ''
            position = random.choice(positions)
            dept = random.choice(departments)
            emp = Employee.objects.create(
                user=user,
                last_name=last_name,
                first_name=first_name,
                middle_name=middle_name,
                position=position,
                department=dept,
                phone_internal=fake.numerify('####'),
                phone_mobile=fake.phone_number(),
                is_employed=True,
                notes='Тест'
            )
            employees.append(emp)

        helpdesk_user = User.objects.create_user(
            username='helpdesk',
            email='helpdesk@test.local',
            password='123456'
        )
        helpdesk_emp = Employee.objects.create(
            user=helpdesk_user,
            last_name='Хелпдесков',
            first_name='Хелпдеск',
            position='Специалист поддержки',
            department=departments[0],
            is_helpdesk_member=True,
            is_employed=True,
        )
        employees.append(helpdesk_emp)

        self.stdout.write('Создание типов оборудования')
        asset_categories = [
            ('IT', 'IT-оборудование'),
            ('NETWORK', 'Сетевое оборудование'),
            ('PERIPHERY', 'Периферия'),
            ('PHONE', 'Телефония'),
        ]
        asset_types = []
        type_names = [
            'Ноутбук', 'Монитор', 'Принтер', 'Сканер',
            'Системный блок', 'Коммутатор', 'Маршрутизатор', 'IP-телефон'
        ]
        for name, (cat_code, cat_label) in zip(type_names, asset_categories * 2):
            at, _ = AssetType.objects.get_or_create(
                name=name, defaults={'category': cat_code}
            )
            asset_types.append(at)

        self.stdout.write('Создание оборудования')
        assets = []
        status_choices = ['storage', 'in_use', 'in_repair', 'broken', 'written_off']
        status_weights = [0.3, 0.5, 0.1, 0.08, 0.02]

        for i in range(120):
            inv_number = f'INV-{fake.numerify("######")}'
            serial_number = fake.uuid4()[:8].upper()
            asset_type = random.choice(asset_types)
            status = random.choices(status_choices, weights=status_weights)[0]

            assigned_to = None
            if status == 'in_use':
                assigned_to = random.choice(employees)

            arrival_date = fake.date_between(start_date='-3y', end_date='today')
            warranty_end_date = arrival_date + timedelta(
                days=random.randint(365, 1095)
            )

            asset = Asset.objects.create(
                inventory_number=inv_number,
                serial_number=serial_number,
                asset_type=asset_type,
                name=f'{asset_type.name} {i}',
                status=status,
                assigned_to=assigned_to,
                arrival_date=arrival_date,
                warranty_end_date=warranty_end_date,
                qr_code_id=fake.uuid4(),
                notes=fake.sentence() if random.random() > 0.7 else ''
            )
            assets.append(asset)

        self.stdout.write('Создание заявок')
        ticket_types = ['checkout', 'issue', 'write_off']
        priorities = ['low', 'medium', 'high', 'critical']
        statuses = ['new', 'in_progress', 'closed']

        for _ in range(200):
            requester = random.choice(employees)
            assignee = random.choice(employees + [None])
            ticket_type = random.choice(ticket_types)
            priority = random.choice(priorities)
            status = random.choice(statuses)
            if ticket_type == 'checkout':
                asset_obj = None
            else:
                user_assets = Asset.objects.filter(
                    assigned_to=requester, status='in_use'
                )
                asset_obj = user_assets.first() if user_assets.exists() else None

            subject = f'{fake.word().capitalize()} - {ticket_type}'
            description = fake.paragraph()
            result = fake.paragraph() if status == 'closed' else ''

            created_at = fake.date_time_between(start_date='-60d', end_date='now')
            closed_at = None
            if status == 'closed':
                closed_at = created_at + timedelta(hours=random.randint(1, 72))

            ticket = Ticket.objects.create(
                requester=requester,
                ticket_type=ticket_type,
                priority=priority,
                status=status,
                subject=subject,
                description=description,
                asset=asset_obj,
                assignee=assignee,
                result=result,
                created_at=created_at,
                closed_at=closed_at
            )

        self.stdout.write(self.style.SUCCESS('=== Готово! ==='))
        self.stdout.write(f'- Отделов: {len(departments)}')
        self.stdout.write(f'- Сотрудников: {len(employees)}')
        self.stdout.write(f'- Оборудования: {len(assets)}')
        self.stdout.write(f'- Заявок: 200')
        self.stdout.write('\nДля входа в админку:')
        self.stdout.write('  username: admin')
        self.stdout.write('  password: (задать через createsuperuser)')
        self.stdout.write('\nДля HelpDesk: helpdesk / 123456')
        self.stdout.write('Для обычных: user_001 / 123456 (и т.д.)')