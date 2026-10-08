from django.urls import path
from . import staff

urlpatterns = [
    path('images/upload/', staff.editor_image_upload, name='staff-image-upload'),
    path('messages/', staff.contact_messages, name='staff-messages'),
    path('messages/<int:pk>/', staff.contact_message, name='staff-message'),
    path('messages/<int:pk>/delete/', staff.contact_message_delete, name='staff-message-delete'),
    path('login/', staff.StaffLoginView.as_view(), name='staff-login'),
    path('logout/', staff.sign_out, name='staff-logout'),
    path('', staff.dashboard, name='staff-home'),
    path('settings/', staff.school_settings, name='staff-settings'),
    path('password/', staff.password_change, name='staff-password'),
    path('team/', staff.team, name='staff-team'),
    path('team/<int:pk>/toggle/', staff.toggle_staff, name='staff-toggle-user'),
    path('applications/', staff.applications, name='staff-applications'),
    path('applications/<int:pk>/', staff.application_detail, name='staff-application'),
    path('applications/<int:pk>/delete/', staff.application_delete, name='staff-application-delete'),
    path('content/<slug:section>/', staff.content_list, name='staff-list'),
    path('content/<slug:section>/new/', staff.content_edit, name='staff-create'),
    path('content/<slug:section>/<int:pk>/', staff.content_edit, name='staff-edit'),
    path('content/<slug:section>/<int:pk>/delete/', staff.content_delete, name='staff-delete'),
]
