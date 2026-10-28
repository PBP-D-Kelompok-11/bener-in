from django.contrib import admin

from .models import RepairPlace, SavedPlace


@admin.register(RepairPlace)
class RepairPlaceAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'osm_type', 'osm_id', 'fetched_at')
    list_filter = ('category',)
    search_fields = ('name', 'address')


@admin.register(SavedPlace)
class SavedPlaceAdmin(admin.ModelAdmin):
    list_display = ('place', 'customer', 'status', 'created_at', 'deleted_at')
    list_filter = ('status',)

    def get_queryset(self, request):
        # Admin perlu melihat juga data yang sudah di-soft-delete.
        return SavedPlace.all_objects.select_related('place', 'customer')
