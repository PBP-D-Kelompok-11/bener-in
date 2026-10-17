from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import get_resolver, resolve, reverse
from django.utils import timezone

from authentication.models import Customer, KategoriBarang, MitraReparasi
from mitra.models import Mitra

from .models import RepairRequest, RepairStatusHistory


class RepairFoundationTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create_user(
            username='customer', password='test-password',
            nama_lengkap='Customer', no_hp='0811',
        )
        self.other_customer = Customer.objects.create_user(
            username='other-customer', password='test-password',
            nama_lengkap='Other Customer', no_hp='0812',
        )
        self.mitra = MitraReparasi.objects.create_user(
            username='partner', password='test-password',
            nama_lengkap='Partner', no_hp='0813', nama_usaha='Repair Shop',
            layanan=[KategoriBarang.GADGET], alamat='Jakarta',
            latitude='-6.200000', longitude='106.816666',
        )
        self.other_mitra = MitraReparasi.objects.create_user(
            username='other-partner', password='test-password',
            nama_lengkap='Other Partner', no_hp='0814', nama_usaha='Other Shop',
            layanan=[KategoriBarang.GADGET], alamat='Jakarta',
            latitude='-6.200000', longitude='106.816666',
        )

    def make_request(self):
        return RepairRequest.objects.create(
            customer=self.customer, mitra=self.mitra,
            category=KategoriBarang.GADGET,
            item_name=' Phone ', description=' Screen is cracked. ',
        )

    def test_new_request_starts_pending_with_customer_history(self):
        repair = self.make_request()
        event = repair.status_history.get()
        self.assertEqual(repair.status, RepairRequest.Status.PENDING)
        self.assertEqual(repair.item_name, 'Phone')
        self.assertEqual(repair.description, 'Screen is cracked.')
        self.assertIsNone(event.from_status)
        self.assertEqual(event.to_status, RepairRequest.Status.PENDING)
        self.assertEqual(event.customer_actor, self.customer)
        self.assertIsNone(event.mitra_actor)
        self.assertTrue(timezone.is_aware(event.occurred_at))
        self.assertFalse(repair.is_successful)

    def test_category_and_accounts_are_fixed_after_submission(self):
        repair = self.make_request()
        for field, value in (
            ('category', KategoriBarang.SEPEDA),
            ('mitra', self.other_mitra),
            ('customer', self.other_customer),
        ):
            with self.subTest(field=field):
                setattr(repair, field, value)
                with self.assertRaises(ValidationError):
                    repair.save()
                repair.refresh_from_db()
        self.assertEqual(repair.status_history.count(), 1)

    def test_only_pending_details_can_be_edited(self):
        repair = self.make_request()
        repair.item_name = 'Tablet'
        repair.description = 'Battery does not charge.'
        repair.save()
        self.assertEqual(repair.item_name, 'Tablet')
        self.assertEqual(repair.status_history.count(), 1)
        repair.transition_to(RepairRequest.Status.ACCEPTED, self.mitra)
        repair.item_name = 'Another item'
        with self.assertRaises(ValidationError):
            repair.save()
        repair.refresh_from_db()
        self.assertEqual(repair.item_name, 'Tablet')

    def test_invalid_creation_and_direct_status_change_are_refused(self):
        with self.assertRaises(ValidationError):
            RepairRequest.objects.create(
                customer=self.customer, mitra=self.mitra,
                category=KategoriBarang.GADGET,
                item_name='Phone', description='Broken',
                status=RepairRequest.Status.COMPLETED,
            )
        self.mitra.is_active = False
        self.mitra.save()
        with self.assertRaises(ValidationError):
            self.make_request()
        self.mitra.is_active = True
        self.mitra.save()
        repair = self.make_request()
        repair.status = RepairRequest.Status.COMPLETED
        with self.assertRaises(ValidationError):
            repair.save()
        repair.refresh_from_db()
        self.assertEqual(repair.status, RepairRequest.Status.PENDING)

    def test_completed_flow_has_one_event_per_transition(self):
        repair = self.make_request()
        for status in (
            RepairRequest.Status.ACCEPTED,
            RepairRequest.Status.IN_PROGRESS,
            RepairRequest.Status.COMPLETED,
        ):
            event = repair.transition_to(status, self.mitra)
            self.assertEqual(event.to_status, status)
            self.assertEqual(event.mitra_actor, self.mitra)
            self.assertTrue(timezone.is_aware(event.occurred_at))
        self.assertEqual(
            list(repair.status_history.values_list('to_status', flat=True)),
            ['pending', 'accepted', 'in_progress', 'completed'],
        )
        self.assertTrue(repair.is_successful)
        with self.assertRaises(ValidationError):
            repair.transition_to(RepairRequest.Status.ACCEPTED, self.mitra)

    def test_cancel_is_soft_and_customer_owned(self):
        repair = self.make_request()
        event = repair.transition_to(RepairRequest.Status.CANCELLED, self.customer)
        self.assertEqual(event.customer_actor, self.customer)
        self.assertEqual(repair.status, RepairRequest.Status.CANCELLED)
        self.assertTrue(RepairRequest.objects.filter(pk=repair.pk).exists())
        self.assertEqual(repair.status_history.count(), 2)
        self.assertFalse(repair.is_successful)
        with self.assertRaises(ValidationError):
            repair.delete()

    def test_rejection_and_unable_to_repair_require_reasons(self):
        for starting_status, outcome in (
            (RepairRequest.Status.PENDING, RepairRequest.Status.REJECTED),
            (RepairRequest.Status.ACCEPTED, RepairRequest.Status.UNABLE_TO_REPAIR),
            (RepairRequest.Status.IN_PROGRESS, RepairRequest.Status.UNABLE_TO_REPAIR),
        ):
            with self.subTest(starting_status=starting_status, outcome=outcome):
                repair = self.make_request()
                if starting_status != RepairRequest.Status.PENDING:
                    repair.transition_to(RepairRequest.Status.ACCEPTED, self.mitra)
                if starting_status == RepairRequest.Status.IN_PROGRESS:
                    repair.transition_to(RepairRequest.Status.IN_PROGRESS, self.mitra)
                count = repair.status_history.count()
                with self.assertRaises(ValidationError):
                    repair.transition_to(outcome, self.mitra, reason='   ')
                repair.refresh_from_db()
                self.assertEqual(repair.status, starting_status)
                self.assertEqual(repair.status_history.count(), count)
                event = repair.transition_to(outcome, self.mitra, reason='  Parts unavailable.  ')
                self.assertEqual(event.reason, 'Parts unavailable.')
                self.assertEqual(event.mitra_actor, self.mitra)
                self.assertFalse(repair.is_successful)

    def test_wrong_actor_and_invalid_transition_are_refused(self):
        repair = self.make_request()
        for status, actor in (
            (RepairRequest.Status.ACCEPTED, self.customer),
            (RepairRequest.Status.ACCEPTED, self.other_mitra),
            (RepairRequest.Status.CANCELLED, self.other_customer),
            (RepairRequest.Status.COMPLETED, self.mitra),
        ):
            with self.subTest(status=status, actor=actor):
                with self.assertRaises(ValidationError):
                    repair.transition_to(status, actor)
        self.assertEqual(repair.status_history.count(), 1)
        self.assertEqual(repair.status, RepairRequest.Status.PENDING)

    def test_stale_transition_and_failed_history_write_do_not_change_status(self):
        repair = self.make_request()
        stale = RepairRequest.objects.get(pk=repair.pk)
        with patch.object(RepairStatusHistory, 'save', side_effect=RuntimeError('write failed')):
            with self.assertRaises(RuntimeError):
                repair.transition_to(RepairRequest.Status.ACCEPTED, self.mitra)
        repair.refresh_from_db()
        self.assertEqual(repair.status, RepairRequest.Status.PENDING)
        self.assertEqual(repair.status_history.count(), 1)
        repair.transition_to(RepairRequest.Status.ACCEPTED, self.mitra)
        with self.assertRaises(ValidationError):
            stale.transition_to(RepairRequest.Status.REJECTED, self.mitra, reason='No parts')
        self.assertEqual(repair.status_history.count(), 2)

    def test_history_is_append_only(self):
        event = self.make_request().status_history.get()
        event.reason = 'changed'
        with self.assertRaises(ValidationError):
            event.save()
        with self.assertRaises(ValidationError):
            event.delete()

    def test_session_backend_keeps_account_types_separate(self):
        self.assertIs(get_user_model(), Customer)
        self.assertIs(RepairRequest._meta.get_field('mitra').remote_field.model, MitraReparasi)
        self.assertIs(Mitra._meta.get_field('user').remote_field.model, Customer)
        self.assertEqual(self.customer.pk, self.mitra.pk)

        self.assertTrue(self.client.login(username='partner', password='test-password'))
        self.assertEqual(
            self.client.session['_auth_user_backend'],
            'authentication.backends.MitraBackend',
        )
        self.assertIsInstance(self.client.get('/').wsgi_request.user, MitraReparasi)
        self.client.logout()
        self.assertTrue(self.client.login(username='customer', password='test-password'))
        self.assertEqual(
            self.client.session['_auth_user_backend'],
            'authentication.backends.CustomerBackend',
        )
        self.assertIsInstance(self.client.get('/').wsgi_request.user, Customer)

    def test_existing_login_view_and_url_namespace(self):
        response = self.client.post('/login/', {
            'username': 'partner', 'password': 'test-password',
        })
        self.assertEqual(response.status_code, 302)
        self.assertIsInstance(self.client.get('/').wsgi_request.user, MitraReparasi)
        self.assertIn('repair', get_resolver().namespace_dict)
        self.assertEqual(resolve('/login/').url_name, 'login')
        self.assertEqual(resolve('/reviews/impact/').url_name, 'impact')


class RepairCreationViewTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create_user(
            username='requester', password='test-password',
            nama_lengkap='Requester', no_hp='0811',
        )
        self.other_customer = Customer.objects.create_user(
            username='another-requester', password='test-password',
            nama_lengkap='Another', no_hp='0812',
        )
        self.mitra = MitraReparasi.objects.create_user(
            username='gadget-partner', password='test-password',
            nama_lengkap='Gadget Partner', no_hp='0813',
            nama_usaha='Bengkel Gadget', layanan=[KategoriBarang.GADGET],
            alamat='Jakarta', latitude='-6.200000', longitude='106.816666',
        )
        self.fallback_mitra = MitraReparasi.objects.create_user(
            username='bike-partner', password='test-password',
            nama_lengkap='Bike Partner', no_hp='0814',
            nama_usaha='Bengkel Sepeda', layanan=[KategoriBarang.SEPEDA],
            alamat='Depok', latitude='-6.400000', longitude='106.800000',
        )
        self.client.force_login(
            self.customer, backend='authentication.backends.CustomerBackend',
        )

    def payload(self, token=None, **overrides):
        if token is None:
            token = self.client.get(reverse('repair:create')).context['token']
        data = {
            'submission_token': token,
            'category': KategoriBarang.GADGET,
            'mitra': str(self.mitra.pk),
            'item_name': 'Ponsel',
            'description': 'Layar retak setelah terjatuh.',
            'action': 'submit',
        }
        data.update(overrides)
        return data

    def test_customer_only_access_and_anonymous_redirect(self):
        self.client.logout()
        response = self.client.get(reverse('repair:create'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response['Location'])
        self.assertIn('next=', response['Location'])
        self.client.force_login(
            self.mitra, backend='authentication.backends.MitraBackend',
        )
        self.assertEqual(self.client.get(reverse('repair:create')).status_code, 403)
        self.assertEqual(self.client.post(reverse('repair:create'), self.payload(token='forged')).status_code, 403)
        self.assertEqual(RepairRequest.objects.count(), 0)
        self.client.force_login(
            self.customer, backend='authentication.backends.CustomerBackend',
        )
        self.assertEqual(self.client.get(reverse('repair:create')).status_code, 200)

    def test_category_matching_and_fallback_use_active_registered_accounts(self):
        inactive = MitraReparasi.objects.create_user(
            username='inactive', password='test-password', nama_lengkap='Inactive',
            no_hp='0815', nama_usaha='Inactive Shop',
            layanan=[KategoriBarang.GADGET], alamat='Bogor',
            latitude='-6.600000', longitude='106.800000', is_active=False,
        )
        token = self.client.get(reverse('repair:create')).context['token']
        response = self.client.post(reverse('repair:create'), {
            'submission_token': token,
            'category': KategoriBarang.GADGET,
            'action': 'refresh_partners',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual([card['pk'] for card in response.context['matching_partners']], [self.mitra.pk])
        self.assertEqual([card['pk'] for card in response.context['other_partners']], [self.fallback_mitra.pk])
        self.assertNotContains(response, inactive.nama_usaha)
        self.assertContains(response, 'Mitra aktif lainnya')
        self.assertFalse(response.context['form'].errors)

    def test_valid_creation_and_owned_confirmation(self):
        response = self.client.post(reverse('repair:create'), self.payload(
            customer=str(self.other_customer.pk), status=RepairRequest.Status.COMPLETED,
        ))
        repair = RepairRequest.objects.get()
        self.assertRedirects(
            response, reverse('repair:confirmation', kwargs={'pk': repair.pk}),
        )
        self.assertEqual(repair.customer, self.customer)
        self.assertEqual(repair.mitra, self.mitra)
        self.assertEqual(repair.category, KategoriBarang.GADGET)
        self.assertEqual(repair.status, RepairRequest.Status.PENDING)
        event = repair.status_history.get()
        self.assertEqual(event.to_status, RepairRequest.Status.PENDING)
        self.assertEqual(event.customer_actor, self.customer)
        self.assertTrue(timezone.is_aware(event.occurred_at))
        self.assertContains(self.client.get(response['Location']), self.mitra.nama_usaha)

    def test_double_submission_returns_original_confirmation(self):
        data = self.payload()
        first = self.client.post(reverse('repair:create'), data)
        second = self.client.post(reverse('repair:create'), data)
        self.assertEqual(first.status_code, 302)
        self.assertEqual(second['Location'], first['Location'])
        self.assertEqual(RepairRequest.objects.count(), 1)
        self.assertEqual(RepairStatusHistory.objects.count(), 1)

    def test_invalid_category_and_required_fields_are_rejected(self):
        for changes, field in (
            ({'category': 'not-a-category'}, 'category'),
            ({'category': ''}, 'category'),
            ({'mitra': ''}, 'mitra'),
            ({'item_name': '   '}, 'item_name'),
            ({'description': '   '}, 'description'),
        ):
            with self.subTest(changes=changes):
                response = self.client.post(reverse('repair:create'), self.payload(**changes))
                self.assertEqual(response.status_code, 200)
                self.assertIn(field, response.context['form'].errors)
        self.assertEqual(RepairRequest.objects.count(), 0)

    def test_inactive_nonexistent_and_forged_mitra_are_rejected(self):
        self.fallback_mitra.is_active = False
        self.fallback_mitra.save()
        for mitra_id in (str(self.fallback_mitra.pk), '999999', 'not-an-id'):
            with self.subTest(mitra_id=mitra_id):
                response = self.client.post(reverse('repair:create'), self.payload(mitra=mitra_id))
                self.assertEqual(response.status_code, 200)
                self.assertIn('mitra', response.context['form'].errors)
        self.assertEqual(RepairRequest.objects.count(), 0)

    def test_fallback_partner_can_be_selected_with_clear_label(self):
        response = self.client.post(reverse('repair:create'), self.payload(mitra=str(self.fallback_mitra.pk)))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(RepairRequest.objects.get().mitra, self.fallback_mitra)

    def test_invalid_or_other_customer_token_cannot_create(self):
        response = self.client.post(reverse('repair:create'), self.payload(token='tampered'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].non_field_errors())
        other_token = self.payload()['submission_token']
        self.client.force_login(
            self.other_customer, backend='authentication.backends.CustomerBackend',
        )
        response = self.client.post(reverse('repair:create'), self.payload(token=other_token))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(RepairRequest.objects.count(), 0)

    def test_server_preview_preserves_input_without_creating(self):
        data = self.payload(action='preview')
        response = self.client.post(reverse('repair:create'), data)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['preview'])
        self.assertContains(response, 'Layar retak setelah terjatuh.')
        self.assertEqual(RepairRequest.objects.count(), 0)
        data['action'] = 'submit'
        self.assertEqual(self.client.post(reverse('repair:create'), data).status_code, 302)
        self.assertEqual(RepairRequest.objects.count(), 1)

    def test_no_javascript_category_refresh_clears_previous_mitra(self):
        token = self.payload()['submission_token']
        first = self.client.post(reverse('repair:create'), self.payload(
            token=token, action='refresh_partners', displayed_category='',
        ))
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.context['form']['mitra'].value(), str(self.mitra.pk))
        second = self.client.post(reverse('repair:create'), self.payload(
            token=token, action='refresh_partners',
            category=KategoriBarang.SEPEDA,
            displayed_category=KategoriBarang.GADGET,
        ))
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.context['form']['mitra'].value(), '')
        self.assertEqual(RepairRequest.objects.count(), 0)

        submitted = self.client.post(reverse('repair:create'), self.payload(
            token=token, category=KategoriBarang.SEPEDA,
            displayed_category=KategoriBarang.GADGET,
        ))
        self.assertIn('mitra', submitted.context['form'].errors)
        self.assertEqual(RepairRequest.objects.count(), 0)

    def test_confirmation_is_private(self):
        repair = RepairRequest.objects.create(
            customer=self.customer, mitra=self.mitra,
            category=KategoriBarang.GADGET,
            item_name='Ponsel', description='Layar retak.',
        )
        url = reverse('repair:confirmation', kwargs={'pk': repair.pk})
        self.client.force_login(
            self.other_customer, backend='authentication.backends.CustomerBackend',
        )
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(
            self.mitra, backend='authentication.backends.MitraBackend',
        )
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 302)
