from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APIClient, APITestCase

from authentication.models import Customer, MitraReparasi


@override_settings(
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
)
class MobileSessionTests(APITestCase):
    password = 'checkpoint-test-password'

    @classmethod
    def setUpTestData(cls):
        cls.customer = Customer.objects.create_user(
            username='mobile-customer',
            password=cls.password,
            nama_lengkap='Customer Uji',
        )
        cls.mitra = MitraReparasi.objects.create_user(
            pk=cls.customer.pk,
            username='mobile-mitra',
            password=cls.password,
            nama_lengkap='Mitra Uji',
            nama_usaha='Bengkel Uji',
            alamat='Depok',
            latitude=-6.36,
            longitude=106.83,
        )

    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=True)

    def _csrf_token(self):
        response = self.client.get(reverse('mobile_api:csrf'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('csrftoken', self.client.cookies)
        return response.data['csrf_token']

    def _login(self, username, password, token):
        return self.client.post(
            reverse('mobile_api:login'),
            {'username': username, 'password': password},
            format='json',
            HTTP_X_CSRFTOKEN=token,
        )

    def test_login_and_me_for_both_roles_with_same_id(self):
        for account in (self.customer, self.mitra):
            with self.subTest(role=account.role):
                self.client = APIClient(enforce_csrf_checks=True)
                login_response = self._login(
                    account.username, self.password, self._csrf_token(),
                )
                self.assertEqual(login_response.status_code, 200)
                self.assertIn('sessionid', self.client.cookies)

                me = self.client.get(reverse('mobile_api:me'))
                self.assertEqual(me.status_code, 200)
                self.assertEqual(me.data, {
                    'id': account.pk,
                    'username': account.username,
                    'nama_lengkap': account.nama_lengkap,
                    'role': account.role,
                })
                self.assertEqual(login_response.data['user'], me.data)

    def test_login_requires_csrf(self):
        self._csrf_token()
        response = self.client.post(
            reverse('mobile_api:login'),
            {'username': self.customer.username, 'password': self.password},
            format='json',
        )
        self.assertEqual(response.status_code, 403)
        self.assertNotIn('sessionid', self.client.cookies)

    def test_invalid_password_does_not_start_session(self):
        response = self._login(
            self.customer.username, 'invalid', self._csrf_token(),
        )
        self.assertEqual(response.status_code, 400)
        self.assertNotIn('sessionid', self.client.cookies)

    def test_me_requires_session(self):
        response = self.client.get(reverse('mobile_api:me'))
        self.assertEqual(response.status_code, 403)

    def test_logout_requires_rotated_csrf_token_and_ends_session(self):
        original_token = self._csrf_token()
        logged_in = self._login(self.customer.username, self.password, original_token)
        self.assertEqual(logged_in.status_code, 200)

        logout_url = reverse('mobile_api:logout')
        stale = self.client.post(logout_url, HTTP_X_CSRFTOKEN=original_token)
        self.assertEqual(stale.status_code, 403)
        logged_out = self.client.post(
            logout_url, HTTP_X_CSRFTOKEN=logged_in.data['csrf_token'],
        )
        self.assertEqual(logged_out.status_code, 204)
        self.assertEqual(self.client.get(reverse('mobile_api:me')).status_code, 403)
