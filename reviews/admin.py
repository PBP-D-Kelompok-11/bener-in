from django.contrib import admin

from .models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('repair_request', 'mitra', 'customer', 'rating', 'created_at')
    list_filter = ('rating',)
    list_select_related = ('repair_request__mitra', 'repair_request__customer')
    search_fields = ('repair_request__item_name', 'comment')
    readonly_fields = ('created_at', 'updated_at')