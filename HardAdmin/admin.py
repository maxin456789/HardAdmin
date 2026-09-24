from django.contrib import admin
from django.utils import timezone
from django.contrib import messages
from HardAdmin.models import Department, Employee, AssetType, Asset, Ticket


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'location', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'location')


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'department', 'position', 'is_employed', 'is_helpdesk_member')
    list_filter = ('department', 'is_employed', 'is_helpdesk_member')
    search_fields = ('last_name', 'first_name', 'middle_name', 'user__username', 'position')


@admin.register(AssetType)
class AssetTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'category')
    list_filter = ('category',)
    search_fields = ('name',)


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ('inventory_number', 'name', 'asset_type', 'status', 'assigned_to')
    list_filter = ('status', 'asset_type', 'asset_type__category', 'assigned_to')
    search_fields = ('inventory_number', 'name', 'serial_number')
    readonly_fields = ('qr_code_id',)

    def get_actions(self, request):
        actions = super().get_actions(request)
        if not request.user.is_superuser:
            actions.pop('action_write_off', None)
        return actions

    @admin.action(description='Списать выбранное оборудование')
    def action_write_off(self, request, queryset):
        non_broken = queryset.exclude(status='broken')
        if non_broken.exists():
            self.message_user(
                request,
                'Списать можно только оборудование со статусом «Неисправен».',
                level=messages.ERROR
            )
            return

        updated = queryset.filter(status='broken').update(
            status='written_off',
            assigned_to=None,
        )
        self.message_user(request, f'Списано устройств: {updated}')

    actions = ['action_write_off']


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ('id', 'ticket_type', 'status', 'requester', 'asset', 'assignee', 'created_at', 'closed_at')
    list_filter = ('status', 'ticket_type', 'priority')
    search_fields = ('subject', 'description', 'requester__last_name', 'asset__inventory_number')
    readonly_fields = ('created_at', 'updated_at', 'closed_at')

    fieldsets = (
        ('Основные данные', {
            'fields': ('requester', 'ticket_type', 'subject', 'description')
        }),
        ('Оборудование и статус', {
            'fields': ('asset', 'status', 'priority', 'assignee')
        }),
        ('Результаты и даты', {
            'fields': ('result', 'notes', 'closed_at')
        }),
    )

    @admin.action(description='Закрыть выбранные заявки')
    def action_close_tickets(self, request, queryset):
        updated = queryset.update(
            status='closed',
            closed_at=timezone.now(),
        )
        self.message_user(request, f'Закрыто заявок: {updated}')

    @admin.action(description='Взять в работу (назначить себя)')
    def action_assign_to_me(self, request, queryset):
        employee = request.user.employee
        updated = queryset.update(
            assignee=employee,
            status='in_progress',
        )
        self.message_user(request, f'Взято в работу: {updated}')

    actions = ['action_close_tickets', 'action_assign_to_me']
