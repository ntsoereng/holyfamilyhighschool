from django.contrib import admin
from .models import SiteSettings, Article, Event, SchoolValue, Application, Department, StaffMember

@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    fieldsets = [('About', {'fields': ('about_heading', 'about_intro', 'about_history', 'about_mission', 'about_vision', 'about_image', 'about_image_alt')}),
        ('Curriculum', {'fields': ('curriculum_heading', 'curriculum_intro', 'curriculum_body', 'curriculum_image', 'curriculum_image_alt')}),
        ('Staff', {'fields': ('staff_heading', 'staff_intro', 'staff_image', 'staff_image_alt')}),
        ('Calendar', {'fields': ('calendar_heading', 'calendar_intro', 'calendar_image', 'calendar_image_alt')}),
        ('Page photographs', {'fields': ('contact_image', 'contact_image_alt', 'admissions_image', 'admissions_image_alt')}),
        ('Identity', {'fields': ('name','motto','logo','demo_mode')}),
        ('Homepage', {'fields': ('hero_eyebrow','hero_title','hero_text','hero_image','hero_image_alt','about_title','about_text')}),
        ('Contact details', {'fields': ('address','office_hours','email','phone','google_maps_embed_url')}),
        ('Admissions & privacy', {'fields': ('admissions_open','admissions_heading','admissions_text','admissions_requirements','privacy_text')}),
        ('Admissions cycle & interview details', {'fields': ('admissions_grade', 'admissions_year', 'admissions_fee',
            'admissions_payment_method', 'admissions_merchant_number', 'admissions_deadline',
            'admissions_interview_date', 'admissions_interview_time', 'admissions_interview_location',
            'admissions_interview_subjects', 'admissions_stationery_note')})]
    def has_add_permission(self, request): return not SiteSettings.objects.exists() and super().has_add_permission(request)
    def has_delete_permission(self, request, obj=None): return False

@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ['title','category','published','published_at']
    list_filter = ['published','category']
    search_fields = ['title','excerpt']
    prepopulated_fields = {'slug': ('title',)}

@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ['title','starts_at','location','published']
    list_filter = ['published','starts_at']
    search_fields = ['title','location']
    prepopulated_fields = {'slug': ('title',)}

@admin.register(SchoolValue)
class SchoolValueAdmin(admin.ModelAdmin):
    list_display = ['title','order']

@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ['learner_name','entry_level','application_year','boarding_required','status','submitted_at']
    list_filter = ['status','entry_level','application_year','boarding_required','district','submitted_at']
    search_fields = ['learner_name','surname','given_name','guardian_name','phone','email','current_school','reference']
    readonly_fields = ['reference','submitted_at','learner_name','surname','given_name','date_of_birth',
        'entry_level','application_year','physical_address','district','district_other','boarding_required',
        'current_school','guardian_name','email','phone','message','consent']
    def has_add_permission(self, request): return False

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ['title', 'published', 'order']
    list_filter = ['published']
    search_fields = ['title', 'description']

@admin.register(StaffMember)
class StaffMemberAdmin(admin.ModelAdmin):
    list_display = ['title', 'honorific', 'position', 'date_from', 'published', 'order']
    list_filter = ['published', 'departments']
    search_fields = ['title', 'honorific', 'position', 'biography']
    filter_horizontal = ['departments']
