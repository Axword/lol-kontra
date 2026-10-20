from django.contrib import admin
from django.urls import path, reverse
from django.utils.html import format_html
from .builder import builder_view
from .models import CommunityComment, Daily, DailySlot, DailySlotCondition

admin.site.site_header = 'WORLDS KONTRA'
admin.site.site_title = 'Panel administratora'
admin.site.index_title = 'Panel administratora'

@admin.register(Daily)
class DailyAdmin(admin.ModelAdmin):
    list_display = ('id', 'date', 'status', 'author_name', 'edit_rules')
    list_filter = ('status', 'reveal_mode')
    date_hierarchy = 'date'
    change_list_template = 'admin/dailies/change_list.html'

    @admin.display(description='Reguły')
    def edit_rules(self, obj):
        return format_html('<a href="{}?daily={}">Edytor reguł</a>', reverse('admin:dailies_daily_builder'), obj.pk)

    def get_urls(self):
        return [path('builder/', self.admin_site.admin_view(lambda request: builder_view(request, self)),
                     name='dailies_daily_builder')] + super().get_urls()

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields] + ['edit_rules']

    def has_add_permission(self, request):
        return False  # All new boards go through the validated editor.

    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(DailySlot)
class DailySlotAdmin(admin.ModelAdmin):
    list_display = ('daily', 'position', 'role')
    list_filter = ('role',)
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(DailySlotCondition)
class DailySlotConditionAdmin(admin.ModelAdmin):
    list_display = ('slot', 'condition_type', 'operator', 'label_pl')
    list_filter = ('condition_type',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CommunityComment)
class CommunityCommentAdmin(admin.ModelAdmin):
    list_display = ('id', 'submission', 'created_at')
    readonly_fields = ('submission', 'share_key', 'roster_png', 'created_at', 'updated_at')

    def has_add_permission(self, request):
        return False
