from django.contrib.auth import SESSION_KEY
from django.test import TestCase
from django.urls import reverse

from .models import Customer, KategoriBarang, MitraReparasi


CUSTOMER_BACKEND = 'authentication.backends.CustomerBackend'
MITRA_BACKEND = 'authentication.backends.MitraBackend'
PASSWORD = 'StrongPass123!'


class AccountModelTests(TestCase):
    def test_customer_name_helpers_and_string_representation(self):
        customer = Customer.objects.create_user(
            username='customer1',
            password=PASSWORD,
            nama_lengkap='Budi Santoso',
            no_hp='081234567890',
        )

        self.assertEqual(customer.get_full_name(), 'Budi Santoso')
        self.assertEqual(customer.get_short_name(), 'Budi')
        self.assertEqual(str(customer), 'Budi Santoso (@customer1)')

    def test_mitra_string_representation(self):
        mitra = MitraReparasi.objects.create_user(
            username='mitra1',
            password=PASSWORD,
            nama_lengkap='Sari Wijaya',
            no_hp='081234567890',
            nama_usaha='Bengkel Sari',
            layanan=[KategoriBarang.GADGET],
            alamat='Jl. Mawar 1',
            latitude='-6.200000',
            longitude='106.800000',
        )

        self.assertEqual(str(mitra), 'Bengkel Sari (@mitra1)')


class RegistrationViewTests(TestCase):
    def customer_data(self, **overrides):
        data = {
            'username': 'newcustomer',
            'nama_lengkap': 'New Customer',
            'email': 'customer@example.com',
            'no_hp': '081234567890',
            'alamat': 'Jl. Contoh 1',
            'password1': PASSWORD,
            'password2': PASSWORD,
        }
        data.update(overrides)
        return data

    def mitra_data(self, **overrides):
        data = {
            'username': 'newmitra',
            'nama_lengkap': 'New Mitra',
            'nama_usaha': 'Bengkel Baru',
            'email': 'mitra@example.com',
            'no_hp': '081234567890',
            'layanan': [KategoriBarang.GADGET, KategoriBarang.MOTOR],
            'alamat': 'Jl. Usaha 2',
            'latitude': '-6.200000',
            'longitude': '106.800000',
            'password1': PASSWORD,
            'password2': PASSWORD,
        }
        data.update(overrides)
        return data

    def test_registration_pages_are_available(self):
        for name in ('register', 'register_customer', 'register_mitra'):
            with self.subTest(url=name):
                response = self.client.get(reverse(f'authentication:{name}'))
                self.assertEqual(response.status_code, 200)

    def test_customer_registration_creates_hashed_user_and_logs_in(self):
        response = self.client.post(
            reverse('authentication:register_customer'),
            self.customer_data(),
        )

        self.assertRedirects(response, '/')
        customer = Customer.objects.get(username='newcustomer')
        self.assertTrue(customer.check_password(PASSWORD))
        self.assertNotEqual(customer.password, PASSWORD)
        self.assertEqual(self.client.session[SESSION_KEY], str(customer.pk))

    def test_mitra_registration_creates_account_with_selected_services(self):
        response = self.client.post(
            reverse('authentication:register_mitra'),
            self.mitra_data(),
        )

        self.assertRedirects(response, '/mitra/profile/')
        mitra = MitraReparasi.objects.get(username='newmitra')
        self.assertEqual(
            mitra.layanan,
            [KategoriBarang.GADGET, KategoriBarang.MOTOR],
        )
        self.assertTrue(mitra.check_password(PASSWORD))
        self.assertEqual(self.client.session[SESSION_KEY], str(mitra.pk))

    def test_registration_rejects_password_mismatch(self):
        response = self.client.post(
            reverse('authentication:register_customer'),
            self.customer_data(password2='DifferentPass123!'),
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('Password tidak sama.', response.context['form'].errors['password2'])
        self.assertFalse(Customer.objects.filter(username='newcustomer').exists())

    def test_registration_rejects_username_used_by_customer(self):
        Customer.objects.create_user(
            username='taken',
            password=PASSWORD,
            nama_lengkap='Existing Customer',
            no_hp='081234567890',
        )

        response = self.client.post(
            reverse('authentication:register_mitra'),
            self.mitra_data(username='taken'),
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('Username ini sudah dipakai.', response.context['form'].errors['username'])
        self.assertFalse(MitraReparasi.objects.filter(username='taken').exists())

    def test_authenticated_user_is_redirected_from_registration(self):
        customer = Customer.objects.create_user(
            username='existing',
            password=PASSWORD,
            nama_lengkap='Existing Customer',
            no_hp='081234567890',
        )
        self.client.force_login(customer, backend=CUSTOMER_BACKEND)

        response = self.client.get(reverse('authentication:register_customer'))

        self.assertRedirects(response, '/')


class AuthenticationViewTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create_user(
            username='customer1',
            password=PASSWORD,
            nama_lengkap='Test Customer',
            no_hp='081234567890',
        )
        self.mitra = MitraReparasi.objects.create_user(
            username='mitra1',
            password=PASSWORD,
            nama_lengkap='Test Mitra',
            no_hp='081234567890',
            nama_usaha='Bengkel Test',
            layanan=[KategoriBarang.MOTOR],
            alamat='Jl. Test 1',
            latitude='-6.200000',
            longitude='106.800000',
        )

    def test_customer_can_log_in_with_customer_backend(self):
        response = self.client.post(
            reverse('authentication:login'),
            {'username': 'customer1', 'password': PASSWORD},
        )

        self.assertRedirects(response, '/')
        self.assertEqual(self.client.session[SESSION_KEY], str(self.customer.pk))

    def test_mitra_can_log_in_with_mitra_backend(self):
        response = self.client.post(
            reverse('authentication:login'),
            {'username': 'mitra1', 'password': PASSWORD},
        )

        self.assertRedirects(response, '/')
        self.assertEqual(self.client.session[SESSION_KEY], str(self.mitra.pk))

    def test_invalid_password_does_not_log_in(self):
        response = self.client.post(
            reverse('authentication:login'),
            {'username': 'customer1', 'password': 'WrongPassword123!'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_logout_redirects_to_home(self):
        self.client.force_login(self.customer, backend=CUSTOMER_BACKEND)

        response = self.client.post(reverse('authentication:logout'))

        self.assertRedirects(response, '/')
        self.assertNotIn(SESSION_KEY, self.client.session)
