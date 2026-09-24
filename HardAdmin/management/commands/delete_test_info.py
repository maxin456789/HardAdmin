from django.core.management.base import BaseCommand
from HardAdmin.models import Ticket, Asset, Employee, Department


class Command(BaseCommand):
    help = 'Очищает тестовые данные из БД (только тестовые записи)'

    def handle(self, *args, **options):
        self.stdout.write('=== Очистка тестовых данных ===')

        # Удаляем только тестовые заявки (тема содержит "Заявка" или "Тест")
        Ticket.objects.filter(subject__icontains='Тест').delete()
        self.stdout.write(f'Удалено - заявки:')

        # Удаляем оборудование с префиксом INV-
        Asset.objects.filter(inventory_number__startswith='INV-').delete()
        self.stdout.write(f'Удалено - оборудование')

        # Удаляем тестовых сотрудников
        from django.contrib.auth.models import User
        test_users = User.objects.filter(username__startswith='user_')
        deleted_emps_count = 0
        for u in test_users:
            try:
                emp = u.employee
                emp.delete()
                deleted_emps_count += 1
            except Employee.DoesNotExist:
                pass
            u.delete()
        self.stdout.write(f'Удалено тестовых пользователей и сотрудников: {deleted_emps_count}')
        test_dept_names = [
            'IT-отдел', 'Бухгалтерия', 'Служба эксплуатации',
            'Отдел кадров', 'Логистика', 'Склад', 'Служба безопасности'
        ]
        Department.objects.filter(name__in=test_dept_names).delete()
        self.stdout.write(f'Удалено - отделы:')
        self.stdout.write(self.style.SUCCESS('=== Очистка завершена ==='))
