from django.urls import reverse
from rest_framework.test import APITestCase

from authentication.models import Customer, KategoriBarang, MitraReparasi
from repair.models import RepairRequest


class MobileModuleTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.customer = Customer.objects.create(username='customer')
        cls.other_customer = Customer.objects.create(username='customer-lain')
        cls.mitra = MitraReparasi.objects.create(
            username='mitra',
            nama_usaha='Bengkel Gadget',
            no_hp='08000000001',
            alamat='Depok',
            latitude='-6.36',
            longitude='106.83',
            layanan=[KategoriBarang.GADGET],
        )
        cls.other_mitra = MitraReparasi.objects.create(
            username='mitra-lain',
            nama_usaha='Bengkel Elektronik',
            alamat='Depok',
            latitude='-6.38',
            longitude='106.83',
            layanan=[KategoriBarang.ELEKTRONIK],
        )
        cls.inactive_mitra = MitraReparasi.objects.create(
            username='mitra-nonaktif',
            nama_usaha='Bengkel Nonaktif',
            alamat='Depok',
            latitude='-6.36',
            longitude='106.83',
            layanan=[KategoriBarang.GADGET],
            is_active=False,
        )
        cls.completed = RepairRequest.objects.create(
            customer=cls.customer,
            mitra=cls.mitra,
            category=KategoriBarang.GADGET,
            item_name='Ponsel',
            description='Layar mati',
        )
        cls.pending = RepairRequest.objects.create(
            customer=cls.customer,
            mitra=cls.other_mitra,
            category=KategoriBarang.ELEKTRONIK,
            item_name='Televisi',
            description='Suara hilang',
        )
        cls.other_completed = RepairRequest.objects.create(
            customer=cls.other_customer,
            mitra=cls.mitra,
            category=KategoriBarang.GADGET,
            item_name='Tablet',
            description='Tidak mengisi daya',
        )
        for repair in (cls.completed, cls.other_completed):
            for next_status in (
                RepairRequest.Status.ACCEPTED,
                RepairRequest.Status.IN_PROGRESS,
                RepairRequest.Status.COMPLETED,
            ):
                repair.transition_to(next_status, cls.mitra)

    def test_repair_list_is_scoped_to_the_customer_or_assigned_mitra(self):
        url = reverse('mobile_api:repairs')
        self.assertEqual(self.client.get(url).status_code, 403)

        for account, expected in (
            (self.customer, {self.completed.pk, self.pending.pk}),
            (self.mitra, {self.completed.pk, self.other_completed.pk}),
        ):
            with self.subTest(role=account.role):
                self.client.force_authenticate(user=account)
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                results = {row['id']: row for row in response.data['results']}
                self.assertEqual(set(results), expected)
                completed = results[self.completed.pk]
                self.assertEqual(completed['mitra_id'], self.mitra.pk)
                self.assertEqual(completed['status'], 'completed')

    def test_partner_detail_exposes_active_partner_and_hides_guest_phone(self):
        url = reverse('mobile_api:mitra-detail', args=[self.mitra.pk])
        guest = self.client.get(url)
        self.assertEqual(guest.status_code, 200)
        self.assertEqual(guest.data['name'], self.mitra.nama_usaha)
        self.assertEqual(guest.data['phone'], '')

        self.client.force_authenticate(user=self.customer)
        customer = self.client.get(url)
        self.assertEqual(customer.data['phone'], self.mitra.no_hp)

        inactive_url = reverse(
            'mobile_api:mitra-detail', args=[self.inactive_mitra.pk],
        )
        self.assertEqual(self.client.get(inactive_url).status_code, 404)

    def test_nearby_filters_by_category_and_shares_partner_ids_with_detail(self):
        url = reverse('mobile_api:mitra-nearby')
        coordinates = {'lat': '-6.36', 'lng': '106.83'}

        nearby = self.client.get(url, coordinates)
        self.assertEqual(nearby.status_code, 200)
        self.assertEqual(
            [partner['id'] for partner in nearby.data['results']],
            [self.mitra.pk, self.other_mitra.pk],
        )

        filtered = self.client.get(url, {**coordinates, 'category': 'gadget'})
        self.assertEqual(filtered.status_code, 200)
        self.assertEqual(len(filtered.data['results']), 1)
        result = filtered.data['results'][0]
        self.assertEqual(result['distance_km'], 0.0)
        detail = self.client.get(
            reverse('mobile_api:mitra-detail', args=[result['id']]),
        )
        self.assertEqual(detail.data['id'], self.mitra.pk)
        self.assertEqual(detail.data['name'], result['name'])

    def test_nearby_rejects_invalid_coordinates_and_radius(self):
        url = reverse('mobile_api:mitra-nearby')
        for parameters in ({'lat': 91, 'lng': 106}, {'lat': 0, 'lng': 0, 'radius_km': 0}):
            with self.subTest(parameters=parameters):
                self.assertEqual(self.client.get(url, parameters).status_code, 400)

    def test_impact_counts_only_completed_repairs_for_signed_in_customer(self):
        url = reverse('mobile_api:impact')
        self.assertEqual(self.client.get(url).status_code, 403)

        self.client.force_authenticate(user=self.mitra)
        self.assertEqual(self.client.get(url).status_code, 403)

        self.client.force_authenticate(user=self.customer)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['saved_count'], 1)
        self.assertEqual(response.data['current_badge']['min'], 1)
        self.assertEqual(response.data['next_badge']['min'], 5)
