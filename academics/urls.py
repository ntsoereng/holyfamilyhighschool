from django.urls import path
from . import views

app_name = 'academics'
urlpatterns = [
    path('', views.home, name='home'),
    path('login/', views.PortalLoginView.as_view(), name='login'),
    path('logout/', views.sign_out, name='logout'),
    path('password/', views.password, name='password'),
    path('marks/<int:pk>/', views.sheet, name='sheet'),
    path('reports/<int:pk>/', views.report, name='report'),
    path('reports/<int:pk>/download/', views.download, name='download'),
    path('office/', views.office, name='office'),
    path('office/accounts/', views.accounts, name='accounts'),
    path('office/accounts/<int:pk>/', views.account, name='account'),
    path('office/family-access/<int:pk>/', views.family_access, name='family-access'),
    path('office/periods/<int:pk>/', views.period_access, name='period'),
    path('office/reports/', views.batch, name='batch'),
    path('office/report-details/<int:enrollment_pk>/<int:period_pk>/', views.report_details, name='report-details'),
    path('office/setup/<slug:section>/<int:pk>/', views.setup_edit, name='setup-edit'),
    path('office/fees/<int:enrollment_pk>/<int:period_pk>/', views.fees, name='fees'),
    path('office/policy/', views.policy, name='policy'),
    path('office/audit/', views.audit_log, name='audit'),
    path('office/setup/<slug:section>/', views.setup, name='setup'),
]
