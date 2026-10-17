from django.test import TestCase
from django.urls import reverse

from authentication.models import Customer, KategoriBarang, MitraReparasi
from repair.models import RepairRequest


class ImpactDashboardTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.customer = Customer.objects.create_user(
            username='impact-customer', password='test-password',
            nama_lengkap='Customer Impact', no_hp='0811',
        )
        cls.other_customer = Customer.objects.create_user(
            username='other-impact-customer', password='test-password',
            nama_lengkap='Other Customer', no_hp='0812',
        )
        cls.mitra = MitraReparasi.objects.create_user(
            username='impact-mitra', password='test-password',
            nama_lengkap='Repair Partner', no_hp='0813',
            nama_usaha='Bengkel Impact', layanan=[KategoriBarang.GADGET],
            alamat='Jakarta', latitude='-6.200000', longitude='106.816666',
        )

    def setUp(self):
        self.url = reverse('reviews:impact')
        self.client.force_login(
            self.customer, backend='authentication.backends.CustomerBackend',
        )

    def make_request(self, customer=None):
        return RepairRequest.objects.create(
            customer=customer or self.customer, mitra=self.mitra,
            category=KategoriBarang.GADGET,
            item_name='Ponsel', description='Layar retak.',
        )

    def complete(self, customer=None):
        repair = self.make_request(customer)
        for status in (
            RepairRequest.Status.ACCEPTED,
            RepairRequest.Status.IN_PROGRESS,
            RepairRequest.Status.COMPLETED,
        ):
            repair.transition_to(status, self.mitra)
        return repair

    def summary(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'reviews/impact_dashboard.html')
        return response.context['summary']

    def test_zero_completed_repairs_and_demo_query_cannot_override_count(self):
        self.assertEqual(self.summary()['saved_count'], 0)
        response = self.client.get(self.url, {'demo': '25'})
        self.assertEqual(response.context['summary']['saved_count'], 0)
        self.assertIsNone(response.context['summary']['current_badge'])

    def test_one_completed_repair_unlocks_first_badge(self):
        self.complete()
        summary = self.summary()
        self.assertEqual(summary['saved_count'], 1)
        self.assertEqual(summary['current_badge']['name'], 'Pemula Peduli')
        self.assertEqual(summary['next_badge']['min'], 5)

    def test_multiple_completed_repairs_keep_existing_progress_calculation(self):
        for _ in range(3):
            self.complete()
        summary = self.summary()
        self.assertEqual(summary['saved_count'], 3)
        self.assertEqual(summary['progress_percent'], 50)
        self.assertEqual(summary['remaining'], 2)

    def test_all_non_completed_statuses_are_excluded(self):
        self.complete()
        self.make_request()  # Pending
        accepted = self.make_request()
        accepted.transition_to(RepairRequest.Status.ACCEPTED, self.mitra)
        in_progress = self.make_request()
        in_progress.transition_to(RepairRequest.Status.ACCEPTED, self.mitra)
        in_progress.transition_to(RepairRequest.Status.IN_PROGRESS, self.mitra)
        rejected = self.make_request()
        rejected.transition_to(RepairRequest.Status.REJECTED, self.mitra, reason='Tidak tersedia.')
        cancelled = self.make_request()
        cancelled.transition_to(RepairRequest.Status.CANCELLED, self.customer)
        unable = self.make_request()
        unable.transition_to(RepairRequest.Status.ACCEPTED, self.mitra)
        unable.transition_to(RepairRequest.Status.UNABLE_TO_REPAIR, self.mitra, reason='Tidak bisa.')
        self.assertEqual(RepairRequest.objects.count(), 7)
        self.assertEqual(self.summary()['saved_count'], 1)

    def test_impact_is_isolated_per_customer(self):
        self.complete()
        self.complete(self.other_customer)
        self.complete(self.other_customer)
        self.assertEqual(self.summary()['saved_count'], 1)
        self.client.force_login(
            self.other_customer, backend='authentication.backends.CustomerBackend',
        )
        self.assertEqual(self.summary()['saved_count'], 2)

    def test_badge_names_and_unlock_thresholds_remain_unchanged(self):
        expected = [
            (1, 'Pemula Peduli', 1, 5),
            (5, 'Penyelamat Barang', 2, 10),
            (10, 'Pahlawan Reparasi', 3, 25),
            (25, 'Duta Repair Before Replace', 4, None),
        ]
        for count in range(1, 26):
            self.complete()
            milestone = next((row for row in expected if row[0] == count), None)
            if milestone is None:
                continue
            with self.subTest(count=count):
                summary = self.summary()
                self.assertEqual(summary['saved_count'], count)
                self.assertEqual(summary['current_badge']['name'], milestone[1])
                self.assertEqual(sum(badge['unlocked'] for badge in summary['badges']), milestone[2])
                self.assertEqual(summary['next_badge']['min'] if summary['next_badge'] else None, milestone[3])
                self.assertEqual(
                    [(badge['name'], badge['min']) for badge in summary['badges']],
                    [
                        ('Pemula Peduli', 1),
                        ('Penyelamat Barang', 5),
                        ('Pahlawan Reparasi', 10),
                        ('Duta Repair Before Replace', 25),
                    ],
                )
                if count == 25:
                    self.assertEqual(summary['progress_percent'], 100)

    def test_refreshes_do_not_count_status_history_as_extra_repairs(self):
        repair = self.complete()
        self.assertEqual(repair.status_history.count(), 4)
        for _ in range(3):
            self.assertEqual(self.summary()['saved_count'], 1)

    def test_mitra_cannot_view_customer_impact_even_with_overlapping_id(self):
        self.complete()
        self.assertEqual(self.customer.pk, self.mitra.pk)
        self.client.force_login(
            self.mitra, backend='authentication.backends.MitraBackend',
        )
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)
        self.assertNotContains(response, 'Pemula Peduli', status_code=403)

    def test_anonymous_user_is_redirected_to_login(self):
        self.client.logout()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response['Location'])
