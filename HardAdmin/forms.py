from django import forms
from HardAdmin.models import Ticket, Asset, Employee, Department


# GET-фильтр для выдачи и списания
class EmployeeFilterForm(forms.Form):
    department = forms.ModelChoiceField(
        queryset=Department.objects.filter(is_active=True).order_by('name'),
        label='Отдел',
        empty_label='— Выберите отдел —',
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    employee = forms.ModelChoiceField(
        queryset=Employee.objects.none(),
        label='Сотрудник',
        empty_label='— Сначала выберите отдел —',
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    def __init__(self, *args, department_id=None, employee_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        # сотрудники подставляются после выбора отдела
        if department_id:
            self.fields['employee'].queryset = (
                Employee.objects.filter(
                    is_employed=True, department_id=department_id
                ).order_by('last_name', 'first_name')
            )
            self.fields['employee'].empty_label = '— Выберите сотрудника —'
            self.fields['department'].initial = department_id
        if employee_id:
            self.fields['employee'].initial = employee_id


# заявка от сотрудника
class TicketForm(forms.ModelForm):
    class Meta:
        model = Ticket
        fields = ['ticket_type', 'priority', 'subject', 'description', 'asset']

    def __init__(self, *args, **kwargs):
        employee = kwargs.pop('employee', None)
        super().__init__(*args, **kwargs)
        for field_name in ['ticket_type', 'priority', 'asset']:
            self.fields[field_name].widget.attrs.update({
                'class': 'form-select', 'style': 'width: 100%;'
            })
        self.fields['subject'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Кратко опишите проблему',
        })
        self.fields['description'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Подробное описание...',
            'rows': 5,
        })
        if employee:
            self.fields['asset'].queryset = Asset.objects.filter(
                assigned_to=employee, status='in_use'
            )
        else:
            self.fields['asset'].queryset = Asset.objects.none()
        self.fields['asset'].required = False
        self.fields['asset'].empty_label = '— Не выбрано —'


# взятие заявки в работу
class TicketAssignForm(forms.ModelForm):
    comment = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 3}),
        label="Комментарий"
    )

    class Meta:
        model = Ticket
        fields = ['priority']
        widgets = {'priority': forms.Select(attrs={'class': 'form-select'})}

    def __init__(self, *args, **kwargs):
        kwargs.pop('employee', None)
        super().__init__(*args, **kwargs)


# закрытие заявки
class TicketResolveForm(forms.Form):
    result = forms.CharField(
        required=True,
        label='Описание решения (обязательно)',
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'placeholder': 'Опишите выполненные действия.',
            'rows': 5,
        }),
    )
    is_working = forms.BooleanField(
        required=False,
        label='Оборудование работоспособно',
    )

    def __init__(self, *args, **kwargs):
        self.ticket = kwargs.pop('ticket', None)
        kwargs.pop('instance', None)
        super().__init__(*args, **kwargs)
        if self.ticket and self.ticket.ticket_type != 'issue':
            self.fields['is_working'].widget = forms.HiddenInput()


# выдача
class AssetAssignForm(forms.Form):
    asset = forms.ModelChoiceField(
        queryset=Asset.objects.none(),
        label='Оборудование (на складе)',
        empty_label='— Выберите устройство —',
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    ticket = forms.ModelChoiceField(
        queryset=Ticket.objects.none(),
        label='Заявка на выдачу (обязательно)',
        empty_label='— Выберите заявку —',
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    def __init__(self, *args, employee_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        if employee_id:
            self.fields['asset'].queryset = (
                Asset.objects.filter(status='storage')
                .select_related('asset_type')
                .order_by('asset_type__name', 'inventory_number')
            )
            self.fields['ticket'].queryset = (
                Ticket.objects.filter(
                    ticket_type='checkout',
                    status__in=['new', 'in_progress'],
                    requester_id=employee_id,
                ).select_related('requester').order_by('-created_at')
            )

    def clean(self):
        cleaned = super().clean()
        asset = cleaned.get('asset')
        ticket = cleaned.get('ticket')
        if asset and asset.status != 'storage':
            raise forms.ValidationError('Оборудование недоступно для выдачи.')
        if not ticket:
            raise forms.ValidationError('Без заявки выдать нельзя.')
        return cleaned


# возврат на склад
class AssetWriteOffForm(forms.Form):
    asset = forms.ModelChoiceField(
        queryset=Asset.objects.none(),
        label='Оборудование (в использовании)',
        empty_label='— Выберите устройство —',
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    ticket = forms.ModelChoiceField(
        queryset=Ticket.objects.none(),
        label='Заявка на списание (обязательно)',
        empty_label='— Выберите заявку —',
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    reason = forms.CharField(
        max_length=500,
        required=True,
        label='Причина списания',
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Укажите причину...',
        }),
    )

    def __init__(self, *args, employee_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        if employee_id:
            self.fields['asset'].queryset = (
                Asset.objects.filter(
                    status='in_use', assigned_to_id=employee_id
                ).select_related('asset_type')
                .order_by('asset_type__name', 'inventory_number')
            )
            self.fields['ticket'].queryset = (
                Ticket.objects.filter(
                    ticket_type='write_off',
                    status__in=['new', 'in_progress'],
                    requester_id=employee_id,
                ).select_related('requester').order_by('-created_at')
            )

    def clean(self):
        cleaned = super().clean()
        asset = cleaned.get('asset')
        ticket = cleaned.get('ticket')
        if asset and asset.status != 'in_use':
            raise forms.ValidationError('Списать можно только оборудование в работе.')
        if not ticket:
            raise forms.ValidationError('Без заявки списать нельзя.')
        return cleaned