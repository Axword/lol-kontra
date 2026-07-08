from django.contrib import admin
from .models import Daily, DailySlot, DailySlotCondition

class DailySlotConditionInline(admin.TabularInline):
    model = DailySlotCondition
    extra = 1

class DailySlotInline(admin.StackedInline):
    model = DailySlot
    extra = 0
    show_change_link = True

@admin.register(Daily)
class DailyAdmin(admin.ModelAdmin):
    list_display = ('id', 'date', 'status', 'reveal_mode', 'published_at')
    list_filter = ('status', 'reveal_mode')
    inlines = [DailySlotInline]
    date_hierarchy = 'date'

@admin.register(DailySlot)
class DailySlotAdmin(admin.ModelAdmin):
    list_display = ('daily', 'position', 'role')
    list_filter = ('role',)
    inlines = [DailySlotConditionInline]

@admin.register(DailySlotCondition)
class DailySlotConditionAdmin(admin.ModelAdmin):
    list_display = ('slot', 'condition_type', 'operator', 'label_pl')
    list_filter = ('condition_type',)
