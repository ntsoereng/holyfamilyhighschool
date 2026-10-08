from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from school import views
from school.sitemaps import sitemap_view, robots_txt
urlpatterns = [
    path('sitemap.xml', sitemap_view, name='sitemap'), path('robots.txt', robots_txt, name='robots-txt'),
    path('staff/', include('school.staff_urls')), path('admin/', admin.site.urls), path('tinymce/', include('tinymce.urls')),
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('curriculum/', views.curriculum, name='curriculum'),
    path('our-staff/', views.staff_directory, name='school-staff'),
    path('our-staff/departments/<int:pk>/', views.department_detail, name='school-department'),
    path('our-staff/profiles/<int:pk>/', views.staff_profile, name='school-staff-profile'),
    path('news/', views.news, name='news'),
    path('news/<slug:slug>/', views.article, name='article'),
    path('events/', views.events, name='events'), path('events/<slug:slug>/', views.event, name='event'),
    path('apply/', views.apply, name='apply'), path('apply/received/', views.application_success, name='application-success'),
    path('contact/', views.contact, name='contact'), path('privacy/', views.privacy, name='privacy'),
    path('subjects/<slug:slug>/', views.subject, name='subject'),
    path('school/<slug:slug>/', views.page, name='page'),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
admin.site.site_header = 'Holy Family · Staff administration'
admin.site.site_title = 'Holy Family'
admin.site.index_title = 'Your school, up to date'

# Routine staff work is handled by the dedicated workspace.
admin.site.has_permission = lambda request: request.user.is_active and request.user.is_staff and request.user.is_superuser

handler404 = 'school.errors.page_not_found'
