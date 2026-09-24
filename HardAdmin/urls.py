from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', views.TicketListView.as_view(), name='index'),
    path('tickets/', views.TicketListView.as_view(), name='ticket_list'),
    path('tickets/new/', views.TicketCreateView.as_view(), name='ticket_create'),
    path('tickets/<int:pk>/', views.TicketDetailView.as_view(), name='ticket_detail'),
    path('tickets/<int:pk>/delete/', views.TicketDeleteView.as_view(), name='ticket_delete'),
    path('tickets/<int:pk>/assign/', views.TicketAssignView.as_view(), name='ticket_assign'),
    path('tickets/<int:pk>/resolve/', views.TicketResolveView.as_view(), name='ticket_resolve'),
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='/'), name='logout'),
    path('helpdesk/', views.HelpDeskListView.as_view(), name='helpdesk_list'),
    path('assets/assign/', views.AssetAssignView.as_view(), name='asset_assign'),
    path('assets/writeoff/', views.AssetWriteOffView.as_view(), name='asset_writeoff'),
    path('assets/registry/', views.AssetRegistryView.as_view(), name='asset_registry'),
    path('assets/<int:pk>/', views.AssetDetailView.as_view(), name='asset_detail'),
    path('employees/registry/', views.EmployeeRegistryView.as_view(), name='employee_registry'),
    path('profile/', views.EmployeeProfileView.as_view(), name='profile'),
]