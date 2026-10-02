from django.contrib import admin

from .models import Customer, MitraReparasi


class AccountAdmin(admin.ModelAdmin):
    search_fields = ('username', 'nama_lengkap', 'no_hp')
    list_filter = ('is_active',)
    exclude = ('groups', 'user_permissions')
    readonly_fields = ('password', 'last_login', 'date_joined')

    def has_add_permission(self, request):
        return False  # akun dibuat lewat halaman register


@admin.register(Customer)
class CustomerAdmin(AccountAdmin):
    list_display = ('username', 'nama_lengkap', 'no_hp', 'is_active')


@admin.register(MitraReparasi)
class MitraReparasiAdmin(AccountAdmin):
    list_display = ('username', 'nama_usaha', 'no_hp', 'is_active')