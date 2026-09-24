from django.db.models import Q, Count
from django.views.generic import (
    ListView, DetailView, CreateView, UpdateView,
    FormView, TemplateView, DeleteView
)
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy, reverse
from django.utils import timezone
from django.shortcuts import redirect
from django.contrib import messages
from HardAdmin.models import Ticket, Employee, Asset, Department, AssetType
from HardAdmin.forms import (
    TicketForm, TicketAssignForm, TicketResolveForm,
    AssetAssignForm, AssetWriteOffForm, EmployeeFilterForm,
)
from HardAdmin.tasks import send_ticket_notification


# список заявок
class TicketListView(LoginRequiredMixin, ListView):
    model = Ticket
    template_name = 'HardAdmin/ticket_list.html'
    context_object_name = 'tickets'
    paginate_by = 10

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if not user.is_authenticated or not hasattr(user, 'employee'):
            return qs.none()
        if not user.employee.is_helpdesk_member:
            return qs.filter(requester=user.employee)
        return qs


# карточка заявки
class TicketDetailView(LoginRequiredMixin, DetailView):
    model = Ticket
    template_name = 'HardAdmin/ticket_detail.html'
    context_object_name = 'ticket'

    def get_queryset(self):
        qs = super().get_queryset()
        employee = self.request.user.employee
        if not employee.is_helpdesk_member:
            qs = qs.filter(requester=employee)
        return qs


# создание заявки
class TicketCreateView(LoginRequiredMixin, CreateView):
    model = Ticket
    form_class = TicketForm
    template_name = 'HardAdmin/ticket_form.html'
    success_url = reverse_lazy('ticket_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['employee'] = self.request.user.employee
        return kwargs

    def form_valid(self, form):
        form.instance.requester = self.request.user.employee
        response = super().form_valid(form)
        if self.object.ticket_type == 'issue' and self.object.asset:
            self.object.asset.status = 'in_repair'
            self.object.asset.save()
            messages.info(
                self.request,
                f'Оборудование {self.object.asset} переведено в ремонт.'
            )
        send_ticket_notification.delay(self.object.pk, 'created')
        return response


# панель helpdesk
class HelpDeskListView(LoginRequiredMixin, ListView):
    model = Ticket
    template_name = 'HardAdmin/helpdesk_list.html'
    context_object_name = 'tickets'

    def dispatch(self, request, *args, **kwargs):
        try:
            if not request.user.employee.is_helpdesk_member:
                messages.error(request, 'Доступ только для HelpDesk')
                return redirect('ticket_list')
        except Employee.DoesNotExist:
            return redirect('ticket_list')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return Ticket.objects.all().select_related(
            'requester', 'asset', 'assignee'
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        employee = self.request.user.employee
        context['new_tickets'] = Ticket.objects.filter(
            status='new'
        ).select_related('requester', 'asset')
        context['my_tickets'] = Ticket.objects.filter(
            assignee=employee,
            status='in_progress'
        ).select_related('requester', 'asset')
        return context


# взять заявку в работу
class TicketAssignView(LoginRequiredMixin, UpdateView):
    model = Ticket
    form_class = TicketAssignForm
    template_name = 'HardAdmin/ticket_assign.html'

    def dispatch(self, request, *args, **kwargs):
        try:
            if not request.user.employee.is_helpdesk_member:
                messages.error(request, 'Доступ только для сотрудников HelpDesk')
                return redirect('ticket_list')
        except Employee.DoesNotExist:
            return redirect('ticket_list')
        ticket = self.get_object()
        if ticket.status != 'new':
            messages.error(request, 'Эта заявка уже взята в работу.')
            return redirect('helpdesk_list')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        ticket = form.instance
        ticket.status = 'in_progress'
        ticket.assignee = self.request.user.employee
        comment = form.cleaned_data.get('comment')
        if comment:
            old_notes = ticket.notes or ""
            ticket.notes = f"{old_notes}\n[HelpDesk] {comment}".strip()
        ticket.save()
        send_ticket_notification.delay(ticket.pk, 'assigned')
        messages.success(
            self.request,
            f'Заявка #{ticket.pk} взята в работу.'
        )
        return redirect('helpdesk_list')

    def get_success_url(self):
        return reverse('helpdesk_list')


# закрытие заявки
class TicketResolveView(LoginRequiredMixin, FormView):
    form_class = TicketResolveForm
    template_name = 'HardAdmin/ticket_resolve.html'
    success_url = reverse_lazy('helpdesk_list')

    def dispatch(self, request, *args, **kwargs):
        try:
            if not request.user.employee.is_helpdesk_member:
                return redirect('ticket_list')
        except Employee.DoesNotExist:
            return redirect('ticket_list')
        self.ticket = Ticket.objects.get(pk=kwargs['pk'])
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['ticket'] = self.ticket
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['ticket'] = self.ticket
        return context

    def form_valid(self, form):
        ticket = self.ticket
        ticket.result = form.cleaned_data['result']
        ticket.status = 'closed'
        ticket.closed_at = timezone.now()
        if not ticket.assignee:
            ticket.assignee = self.request.user.employee
        # для issue: починено -> в работу, нет -> broken на склад
        if ticket.ticket_type == 'issue' and ticket.asset:
            is_working = form.cleaned_data.get('is_working', False)
            if is_working:
                ticket.asset.status = 'in_use'
                messages.info(
                    self.request,
                    f'{ticket.asset} возвращено в работу.'
                )
            else:
                ticket.asset.status = 'broken'
                ticket.asset.assigned_to = None
                messages.info(
                    self.request,
                    f'{ticket.asset} переведено в неисправные и отправлено на склад.'
                )
            ticket.asset.save()
        ticket.save()
        send_ticket_notification.delay(ticket.pk, 'closed')
        messages.success(self.request, f'Заявка #{ticket.pk} закрыта.')
        return super().form_valid(form)


# удаление заявки
class TicketDeleteView(LoginRequiredMixin, DeleteView):
    model = Ticket
    template_name = 'HardAdmin/ticket_delete.html'
    success_url = reverse_lazy('ticket_list')

    def dispatch(self, request, *args, **kwargs):
        try:
            employee = request.user.employee
            ticket = self.get_object()
            if not employee.is_helpdesk_member and ticket.requester != employee:
                messages.error(request, 'Нет прав на удаление этой заявки.')
                return redirect('ticket_list')
        except Employee.DoesNotExist:
            return redirect('ticket_list')
        return super().dispatch(request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        ticket = self.get_object()
        ticket_id = ticket.pk
        response = super().delete(request, *args, **kwargs)
        messages.warning(request, f'Заявка #{ticket_id} удалена.')
        return response


# выдача оборудования по заявке
class AssetAssignView(LoginRequiredMixin, FormView):
    form_class = AssetAssignForm
    template_name = 'HardAdmin/asset_assign.html'
    success_url = reverse_lazy('helpdesk_list')

    def dispatch(self, request, *args, **kwargs):
        try:
            if not request.user.employee.is_helpdesk_member:
                messages.error(request, 'Только для HelpDesk')
                return redirect('ticket_list')
        except Employee.DoesNotExist:
            return redirect('ticket_list')
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['employee_id'] = self.request.GET.get('employee')
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        employee_id = self.request.GET.get('employee')
        context['filter_form'] = EmployeeFilterForm(
            department_id=self.request.GET.get('department'),
            employee_id=employee_id,
        )
        if employee_id:
            try:
                context['selected_employee'] = Employee.objects.get(
                    pk=employee_id, is_employed=True
                )
            except Employee.DoesNotExist:
                context['selected_employee'] = None
        else:
            context['selected_employee'] = None
        return context

    def form_valid(self, form):
        asset = form.cleaned_data['asset']
        ticket = form.cleaned_data['ticket']
        employee_id = self.request.GET.get('employee')
        helpdesk = self.request.user.employee
        try:
            employee = Employee.objects.get(pk=employee_id, is_employed=True)
        except Employee.DoesNotExist:
            form.add_error(None, 'Сотрудник не найден.')
            return self.form_invalid(form)
        asset.status = 'in_use'
        asset.assigned_to = employee
        asset.save()
        ticket.status = 'closed'
        ticket.closed_at = timezone.now()
        ticket.asset = asset
        ticket.assignee = helpdesk
        ticket.save()
        send_ticket_notification.delay(ticket.pk, 'closed')
        messages.success(
            self.request,
            f'{asset} выдано: {employee.full_name}. Заявка #{ticket.pk} закрыта.'
        )
        return super().form_valid(form)


# возврат
class AssetWriteOffView(LoginRequiredMixin, FormView):
    form_class = AssetWriteOffForm
    template_name = 'HardAdmin/asset_writeoff.html'
    success_url = reverse_lazy('helpdesk_list')

    def dispatch(self, request, *args, **kwargs):
        try:
            if not request.user.employee.is_helpdesk_member:
                messages.error(request, 'Только для HelpDesk')
                return redirect('ticket_list')
        except Employee.DoesNotExist:
            return redirect('ticket_list')
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['employee_id'] = self.request.GET.get('employee')
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        employee_id = self.request.GET.get('employee')
        context['filter_form'] = EmployeeFilterForm(
            department_id=self.request.GET.get('department'),
            employee_id=employee_id,
        )
        if employee_id:
            try:
                context['selected_employee'] = Employee.objects.get(
                    pk=employee_id, is_employed=True
                )
            except Employee.DoesNotExist:
                context['selected_employee'] = None
        else:
            context['selected_employee'] = None
        return context

    def form_valid(self, form):
        asset = form.cleaned_data['asset']
        reason = form.cleaned_data['reason']
        ticket = form.cleaned_data['ticket']
        employee_id = self.request.GET.get('employee')
        helpdesk = self.request.user.employee
        try:
            employee = Employee.objects.get(pk=employee_id, is_employed=True)
        except Employee.DoesNotExist:
            form.add_error(None, 'Сотрудник не найден.')
            return self.form_invalid(form)
        asset.status = 'storage'
        asset.assigned_to = None
        old_notes = asset.notes or ''
        asset.notes = f'{old_notes}\nПричина списания: {reason}'.strip()
        asset.save()
        ticket.status = 'closed'
        ticket.closed_at = timezone.now()
        ticket.asset = asset
        ticket.assignee = helpdesk
        ticket.save()
        send_ticket_notification.delay(ticket.pk, 'closed')
        messages.success(
            self.request,
            f'{asset} возвращено на склад. Заявка #{ticket.pk} закрыта.'
        )
        return super().form_valid(form)


# профиль сотрудника
class EmployeeProfileView(LoginRequiredMixin, TemplateView):
    template_name = 'HardAdmin/profile.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        employee = self.request.user.employee
        context['employee'] = employee
        context['assets'] = Asset.objects.filter(
            assigned_to=employee,
            status='in_use'
        ).select_related('asset_type')
        return context


# реестр
class AssetRegistryView(LoginRequiredMixin, ListView):
    model = Asset
    template_name = 'HardAdmin/asset_registry.html'
    context_object_name = 'assets'
    paginate_by = 20

    def get_queryset(self):
        qs = Asset.objects.select_related(
            'asset_type', 'assigned_to', 'assigned_to__department'
        )
        status = self.request.GET.get('status')
        asset_type = self.request.GET.get('type')
        department = self.request.GET.get('department')
        employee = self.request.GET.get('employee')
        q = self.request.GET.get('q')
        if status:
            qs = qs.filter(status=status)
        if asset_type:
            qs = qs.filter(asset_type_id=asset_type)
        if department:
            qs = qs.filter(assigned_to__department_id=department)
        if employee:
            qs = qs.filter(assigned_to_id=employee)
        if q:
            qs = qs.filter(
                Q(inventory_number__icontains=q)
                | Q(name__icontains=q)
                | Q(serial_number__icontains=q)
            )
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_choices'] = Asset.STATUS_CHOICES
        context['asset_types'] = AssetType.objects.all().order_by('name')
        context['departments'] = Department.objects.filter(is_active=True).order_by('name')
        context['current_status'] = self.request.GET.get('status', '')
        context['current_type'] = self.request.GET.get('type', '')
        context['current_department'] = self.request.GET.get('department', '')
        context['q'] = self.request.GET.get('q', '')
        return context


# карточка оборудования
class AssetDetailView(LoginRequiredMixin, DetailView):
    model = Asset
    template_name = 'HardAdmin/asset_detail.html'
    context_object_name = 'asset'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tickets'] = self.object.tickets.select_related(
            'requester', 'assignee'
        ).order_by('-created_at')
        return context


# реестр сотрудников
class EmployeeRegistryView(LoginRequiredMixin, ListView):
    model = Employee
    template_name = 'HardAdmin/employee_registry.html'
    context_object_name = 'employees'
    paginate_by = 20

    def get_queryset(self):
        qs = Employee.objects.select_related('department').annotate(
            assets_count=Count('assets', filter=Q(assets__status='in_use'))
        )
        department = self.request.GET.get('department')
        employed = self.request.GET.get('employed')
        q = self.request.GET.get('q')
        if department:
            qs = qs.filter(department_id=department)
        if employed == '1':
            qs = qs.filter(is_employed=True)
        elif employed == '0':
            qs = qs.filter(is_employed=False)
        if q:
            qs = qs.filter(
                Q(last_name__icontains=q)
                | Q(first_name__icontains=q)
                | Q(middle_name__icontains=q)
                | Q(position__icontains=q)
            )
        return qs.order_by('last_name', 'first_name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['departments'] = Department.objects.filter(is_active=True).order_by('name')
        context['current_department'] = self.request.GET.get('department', '')
        context['current_employed'] = self.request.GET.get('employed', '')
        context['q'] = self.request.GET.get('q', '')
        return context