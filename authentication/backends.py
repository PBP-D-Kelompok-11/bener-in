from django.contrib.auth.backends import BaseBackend

from .models import Customer, MitraReparasi


class AccountBackend(BaseBackend):
    """Backend per model. Backend yang dipakai disimpan di session, jadi id yang
    sama di dua tabel (Customer #1 dan Mitra #1) tidak tertukar."""
    model = None

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None
        try:
            user = self.model._default_manager.get_by_natural_key(username)
        except self.model.DoesNotExist:
            self.model().set_password(password)  # samakan waktu respons
            return None
        if user.is_active and user.check_password(password):
            return user
        return None

    def get_user(self, user_id):
        user = self.model._default_manager.filter(pk=user_id).first()
        return user if user and user.is_active else None


class CustomerBackend(AccountBackend):
    model = Customer


class MitraBackend(AccountBackend):
    model = MitraReparasi