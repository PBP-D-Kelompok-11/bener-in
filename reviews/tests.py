from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from authentication.models import Customer, KategoriBarang, MitraReparasi
from repair.models import RepairRequest

from .impact import get_impact_summary
from .models import Review

CUSTOMER_BACKEND = 'authentication.backends.CustomerBackend'
MITRA_BACKEND = 'authentication.backends.MitraBackend'


class ImpactSummaryTests(SimpleTestCase):
    def test_zero_repairs_has_no_badge(self):
        summary = get_impact_summary(0)
        self.assertIsNone(summary['current_badge'])
        self.assertEqual(summary['next_badge']['min'], 1)
        self.assertEqual(summary['progress_percent'], 0)

    def test_progress_between_badges(self):
        summary = get_impact_summary(7)
        self.assertEqual(summary['current_badge']['name'], 'Penyelamat Barang')
        self.assertEqual(summary['progress_percent'], 40)
        self.assertEqual(summary['remaining'], 3)

    def test_highest_badge_is_full(self):
        summary = get_impact_summary(40)
        self.assertIsNone(summary['next_badge'])
        self.assertEqual(summary['progress_percent'], 100)


class ReviewTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.customer = Customer.objects.create_user(
            username='budi', password='kata-sandi-123',
            nama_lengkap='Budi Santoso', no_hp='0812',
        )
        cls.other = Customer.objects.create_user(
            username='sari', password='kata-sandi-123',
            nama_lengkap='Sari Dewi', no_hp='0813',
        )
        cls.mitra = MitraReparasi.objects.create_user(
            username='bengkel', password='kata-sandi-123',
            nama_lengkap='Pak Joko', no_hp='0814', nama_usaha='Bengkel Joko',
            layanan=[KategoriBarang.GADGET], alamat='Jl. Mawar 1',
            latitude='-6.200000', longitude='106.800000',
        )

    def make_repair(self, completed=True):
        repair = RepairRequest.objects.create(
            customer=self.customer, mitra=self.mitra,
            category=KategoriBarang.GADGET,
            item_name='HP layar retak', description='Layar pecah setelah jatuh',
        )
        if completed:
            for status in (
                RepairRequest.Status.ACCEPTED,
                RepairRequest.Status.IN_PROGRESS,
                RepairRequest.Status.COMPLETED,
            ):
                repair.transition_to(status, self.mitra)
        return repair

    def login_customer(self, user=None):
        self.client.force_login(user or self.customer, backend=CUSTOMER_BACKEND)

    def login_mitra(self):
        self.client.force_login(self.mitra, backend=MITRA_BACKEND)


class ReviewAccessTests(ReviewTestBase):
    def test_anonymous_is_redirected_to_login(self):
        repair = self.make_repair()
        response = self.client.get(reverse('reviews:create', args=[repair.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_mitra_cannot_write_reviews(self):
        repair = self.make_repair()
        self.login_mitra()
        response = self.client.get(reverse('reviews:create', args=[repair.pk]))
        self.assertEqual(response.status_code, 403)

    def test_other_customer_cannot_review_someone_elses_repair(self):
        repair = self.make_repair()
        self.login_customer(self.other)
        response = self.client.get(reverse('reviews:create', args=[repair.pk]))
        self.assertEqual(response.status_code, 404)


class ReviewFlowTests(ReviewTestBase):
    def test_cannot_review_unfinished_repair(self):
        repair = self.make_repair(completed=False)
        self.login_customer()
        response = self.client.post(
            reverse('reviews:create', args=[repair.pk]), {'rating': 5, 'comment': 'x'},
        )
        self.assertRedirects(response, reverse('reviews:mine'))
        self.assertFalse(Review.objects.exists())

    def test_create_review_for_completed_repair(self):
        repair = self.make_repair()
        self.login_customer()
        response = self.client.post(
            reverse('reviews:create', args=[repair.pk]),
            {'rating': 5, 'comment': '  Cepat dan rapi  '},
        )
        self.assertRedirects(response, reverse('reviews:mine'))
        review = Review.objects.get()
        self.assertEqual(review.rating, 5)
        self.assertEqual(review.comment, 'Cepat dan rapi')
        self.assertEqual(review.mitra, self.mitra)

    def test_rating_is_required_and_limited(self):
        repair = self.make_repair()
        self.login_customer()
        for bad in ('', '0', '6'):
            response = self.client.post(
                reverse('reviews:create', args=[repair.pk]), {'rating': bad},
            )
            self.assertEqual(response.status_code, 200)
        self.assertFalse(Review.objects.exists())

    def test_second_attempt_redirects_to_edit(self):
        repair = self.make_repair()
        review = Review.objects.create(repair_request=repair, rating=4)
        self.login_customer()
        response = self.client.get(reverse('reviews:create', args=[repair.pk]))
        self.assertRedirects(response, reverse('reviews:edit', args=[review.pk]))

    def test_edit_and_delete_own_review(self):
        repair = self.make_repair()
        review = Review.objects.create(repair_request=repair, rating=4)
        self.login_customer()
        self.client.post(reverse('reviews:edit', args=[review.pk]), {'rating': 2, 'comment': 'Kurang'})
        review.refresh_from_db()
        self.assertEqual(review.rating, 2)
        self.client.post(reverse('reviews:delete', args=[review.pk]))
        self.assertFalse(Review.objects.exists())

    def test_other_customer_cannot_edit_or_delete(self):
        repair = self.make_repair()
        review = Review.objects.create(repair_request=repair, rating=4)
        self.login_customer(self.other)
        self.assertEqual(self.client.get(reverse('reviews:edit', args=[review.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse('reviews:delete', args=[review.pk])).status_code, 404)
        self.assertTrue(Review.objects.exists())


class MitraReviewsAndImpactTests(ReviewTestBase):
    def test_mitra_page_is_public_and_shows_average(self):
        Review.objects.create(repair_request=self.make_repair(), rating=5)
        Review.objects.create(repair_request=self.make_repair(), rating=4)
        response = self.client.get(reverse('reviews:mitra', args=[self.mitra.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['average'], 4.5)
        self.assertEqual(response.context['total'], 2)

    def test_impact_counts_only_completed_repairs(self):
        self.make_repair(completed=True)
        self.make_repair(completed=False)
        self.login_customer()
        response = self.client.get(reverse('reviews:impact'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['summary']['saved_count'], 1)

    def test_mitra_is_redirected_to_own_review_page(self):
        self.login_mitra()
        response = self.client.get(reverse('reviews:mitra_own'))
        self.assertRedirects(response, reverse('reviews:mitra', args=[self.mitra.pk]))

    def test_customer_cannot_use_mitra_shortcut(self):
        self.login_customer()
        response = self.client.get(reverse('reviews:mitra_own'))
        self.assertEqual(response.status_code, 403)