from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from django.urls import get_resolver, resolve, reverse
from django.utils import timezone

from authentication.models import Customer, KategoriBarang, MitraReparasi
from mitra.models import Mitra

from .forms import RepairRequestEditForm
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

    def test_category_selector_has_no_empty_card(self):
        response = self.client.get(reverse('repair:create'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'value="" name="category"')
        self.assertEqual(
            len(response.context['form'].fields['category'].choices),
            len(KategoriBarang.choices),
        )

    def test_category_without_matching_service_explains_fallback(self):
        token = self.client.get(reverse('repair:create')).context['token']
        response = self.client.post(reverse('repair:create'), {
            'submission_token': token,
            'category': KategoriBarang.PERHIASAN,
            'item_name': 'Cincin',
            'description': 'Pengait lepas.',
            'action': 'refresh_partners',
        })
        self.assertEqual(response.context['matching_partners'], [])
        self.assertContains(response, 'Belum ada mitra yang mencantumkan layanan untuk kategori ini')
        self.assertContains(response, 'value="Cincin"')
        self.assertContains(response, 'data-partner-card')

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


class RepairManagementViewTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create_user(
            username='owner', password='test-password',
            nama_lengkap='Pemilik Barang', no_hp='0811',
        )
        self.other_customer = Customer.objects.create_user(
            username='other-owner', password='test-password',
            nama_lengkap='Pelanggan Lain', no_hp='0812',
        )
        self.mitra = MitraReparasi.objects.create_user(
            username='assigned-partner', password='test-password',
            nama_lengkap='Pemilik Bengkel', no_hp='0813',
            nama_usaha='Bengkel Daun', layanan=[KategoriBarang.GADGET],
            alamat='Jakarta', latitude='-6.200000', longitude='106.816666',
        )
        self.other_mitra = MitraReparasi.objects.create_user(
            username='other-assigned-partner', password='test-password',
            nama_lengkap='Mitra Lain', no_hp='0814',
            nama_usaha='Bengkel Lain', layanan=[KategoriBarang.SEPEDA],
            alamat='Depok', latitude='-6.400000', longitude='106.800000',
        )
        self.client.force_login(
            self.customer, backend='authentication.backends.CustomerBackend',
        )

    def make_request(self, *, customer=None, mitra=None, item_name='Ponsel',
                     category=KategoriBarang.GADGET, description='Layar retak.'):
        return RepairRequest.objects.create(
            customer=customer or self.customer,
            mitra=mitra or self.mitra,
            category=category,
            item_name=item_name, description=description,
        )

    def test_list_shows_only_owned_requests_and_recent_first(self):
        older = self.make_request(item_name='Barang Pertama')
        newer = self.make_request(item_name='Barang Kedua')
        other = self.make_request(customer=self.other_customer, item_name='Barang Rahasia')
        newer.transition_to(RepairRequest.Status.ACCEPTED, self.mitra)
        response = self.client.get(reverse('repair:list'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual([repair.pk for repair in response.context['repairs']], [newer.pk, older.pk])
        self.assertContains(response, 'Barang Pertama')
        self.assertContains(response, 'Barang Kedua')
        self.assertNotContains(response, other.item_name)
        self.assertEqual(
            response.context['repairs'][0].last_status_at,
            newer.status_history.order_by('-pk').first().occurred_at,
        )

    def test_list_status_filter_and_empty_states(self):
        empty = self.client.get(reverse('repair:list'))
        self.assertContains(empty, 'Belum ada permintaan reparasi')
        pending = self.make_request(item_name='Barang Pending')
        accepted = self.make_request(item_name='Barang Accepted')
        accepted.transition_to(RepairRequest.Status.ACCEPTED, self.mitra)
        filtered = self.client.get(reverse('repair:list'), {'status': 'accepted'})
        self.assertEqual([repair.pk for repair in filtered.context['repairs']], [accepted.pk])
        self.assertNotContains(filtered, pending.item_name)
        no_match = self.client.get(reverse('repair:list'), {'status': 'completed'})
        self.assertContains(no_match, 'Tidak ada permintaan berstatus Completed')
        invalid = self.client.get(reverse('repair:list'), {'status': 'invented'})
        self.assertEqual(len(invalid.context['repairs']), 2)

    def test_customer_list_search_category_and_combined_filters(self):
        phone = self.make_request(item_name='Ponsel Retak', description='Baterai panas.')
        bike = self.make_request(
            item_name='Sepeda Kota', category=KategoriBarang.SEPEDA,
            description='Rantai lepas.',
        )
        bike.transition_to(RepairRequest.Status.ACCEPTED, self.mitra)
        hidden = self.make_request(customer=self.other_customer, item_name='Sepeda Rahasia')
        search = self.client.get(reverse('repair:list'), {'q': 'baterai'})
        self.assertEqual([item.pk for item in search.context['repairs']], [phone.pk])
        partner_search = self.client.get(reverse('repair:list'), {'q': self.mitra.nama_usaha})
        self.assertEqual(len(partner_search.context['repairs']), 2)
        category = self.client.get(reverse('repair:list'), {'category': KategoriBarang.SEPEDA})
        self.assertEqual([item.pk for item in category.context['repairs']], [bike.pk])
        combined = self.client.get(reverse('repair:list'), {
            'q': 'kota', 'category': KategoriBarang.SEPEDA, 'status': 'accepted',
        })
        self.assertEqual([item.pk for item in combined.context['repairs']], [bike.pk])
        hidden_search = self.client.get(reverse('repair:list'), {'q': 'rahasia'})
        self.assertEqual(hidden_search.context['result_count'], 0)
        self.assertNotContains(hidden_search, hidden.item_name)

    def test_customer_list_ajax_partial_and_regular_get_fallback(self):
        self.make_request(item_name='Tablet')
        url = reverse('repair:list')
        partial = self.client.get(url, {'q': 'tablet'}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertTemplateUsed(partial, 'repair/_customer_results.html')
        self.assertContains(partial, 'Tablet')
        self.assertContains(partial, 'data-result-count="1"')
        self.assertNotContains(partial, '<html')
        regular = self.client.get(url, {'q': 'tablet', 'status': 'pending'})
        self.assertTemplateUsed(regular, 'repair/request_list.html')
        self.assertContains(regular, 'value="tablet"')
        self.assertContains(regular, 'value="pending" selected')
        self.assertContains(regular, 'data-customer-results')
        self.assertContains(regular, 'aria-live="polite"')
        self.assertContains(regular, 'js/repair.js')

    def test_list_anonymous_and_mitra_are_restricted(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse('repair:list')).status_code, 302)
        self.assertEqual(self.client.get(
            reverse('repair:list'), HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        ).status_code, 302)
        self.client.force_login(self.mitra, backend='authentication.backends.MitraBackend')
        self.assertEqual(self.client.get(reverse('repair:list')).status_code, 403)
        self.assertEqual(self.client.get(
            reverse('repair:list'), HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        ).status_code, 403)

    def test_detail_only_owner_or_assigned_mitra_can_view(self):
        repair = self.make_request()
        url = reverse('repair:detail', kwargs={'pk': repair.pk})
        self.assertContains(self.client.get(url), 'Layar retak.')
        self.client.force_login(
            self.other_customer, backend='authentication.backends.CustomerBackend',
        )
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(self.other_mitra, backend='authentication.backends.MitraBackend')
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(self.mitra, backend='authentication.backends.MitraBackend')
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 302)

    def test_detail_displays_only_actual_history_with_actor_and_reason(self):
        repair = self.make_request()
        repair.transition_to(RepairRequest.Status.REJECTED, self.mitra, reason='Komponen tidak tersedia.')
        response = self.client.get(reverse('repair:detail', kwargs={'pk': repair.pk}))
        self.assertEqual([event.to_status for event in response.context['history']], [
            RepairRequest.Status.PENDING, RepairRequest.Status.REJECTED,
        ])
        self.assertContains(response, 'Rejected')
        self.assertContains(response, 'Komponen tidak tersedia.')
        self.assertContains(response, 'Bengkel Daun')
        self.assertNotContains(response, 'In Progress')
        self.assertFalse(response.context['can_manage'])

    def test_terminal_outcomes_are_distinct_and_not_editable(self):
        cancelled = self.make_request(item_name='Barang Cancelled')
        cancelled.transition_to(RepairRequest.Status.CANCELLED, self.customer)
        unable = self.make_request(item_name='Barang Unable')
        unable.transition_to(RepairRequest.Status.ACCEPTED, self.mitra)
        unable.transition_to(RepairRequest.Status.UNABLE_TO_REPAIR, self.mitra, reason='Kerusakan terlalu berat.')
        completed = self.make_request(item_name='Barang Completed')
        completed.transition_to(RepairRequest.Status.ACCEPTED, self.mitra)
        completed.transition_to(RepairRequest.Status.IN_PROGRESS, self.mitra)
        completed.transition_to(RepairRequest.Status.COMPLETED, self.mitra)
        for repair, label in ((cancelled, 'Cancelled'), (unable, 'Unable to Repair'), (completed, 'Completed')):
            with self.subTest(label=label):
                response = self.client.get(reverse('repair:detail', kwargs={'pk': repair.pk}))
                self.assertContains(response, label)
                self.assertFalse(response.context['can_manage'])
        self.assertContains(
            self.client.get(reverse('repair:detail', kwargs={'pk': unable.pk})),
            'Kerusakan terlalu berat.',
        )

    def test_pending_edit_changes_only_allowed_fields_and_no_status_history(self):
        repair = self.make_request()
        original_event = repair.status_history.get()
        response = self.client.post(reverse('repair:edit', kwargs={'pk': repair.pk}), {
            'item_name': 'Tablet',
            'description': 'Baterai tidak mengisi.',
            'category': KategoriBarang.SEPEDA,
            'mitra': str(self.other_mitra.pk),
            'status': RepairRequest.Status.COMPLETED,
            'customer': str(self.other_customer.pk),
        })
        self.assertRedirects(
            response, reverse('repair:detail', kwargs={'pk': repair.pk}),
            fetch_redirect_response=False,
        )
        repair.refresh_from_db()
        self.assertEqual(repair.item_name, 'Tablet')
        self.assertEqual(repair.description, 'Baterai tidak mengisi.')
        self.assertEqual(repair.category, KategoriBarang.GADGET)
        self.assertEqual(repair.mitra, self.mitra)
        self.assertEqual(repair.customer, self.customer)
        self.assertEqual(repair.status, RepairRequest.Status.PENDING)
        self.assertEqual(repair.status_history.count(), 1)
        self.assertEqual(repair.status_history.get().occurred_at, original_event.occurred_at)
        self.assertContains(self.client.get(reverse('repair:detail', kwargs={'pk': repair.pk})), 'berhasil diperbarui')

    def test_edit_validation_and_permissions(self):
        repair = self.make_request()
        url = reverse('repair:edit', kwargs={'pk': repair.pk})
        invalid = self.client.post(url, {'item_name': '   ', 'description': '   '})
        self.assertEqual(invalid.status_code, 200)
        self.assertIn('item_name', invalid.context['form'].errors)
        self.assertIn('description', invalid.context['form'].errors)
        self.client.force_login(
            self.other_customer, backend='authentication.backends.CustomerBackend',
        )
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(self.mitra, backend='authentication.backends.MitraBackend')
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(
            self.customer, backend='authentication.backends.CustomerBackend',
        )
        repair.transition_to(RepairRequest.Status.ACCEPTED, self.mitra)
        self.assertEqual(self.client.get(url).status_code, 403)
        posted = self.client.post(url, {'item_name': 'Diubah', 'description': 'Diubah juga'})
        self.assertRedirects(posted, reverse('repair:detail', kwargs={'pk': repair.pk}))
        repair.refresh_from_db()
        self.assertEqual(repair.item_name, 'Ponsel')

    def test_edit_handles_status_change_during_save(self):
        repair = self.make_request()
        original_save = RepairRequestEditForm.save

        def accept_then_save(form, *args, **kwargs):
            current = RepairRequest.objects.get(pk=repair.pk)
            current.transition_to(RepairRequest.Status.ACCEPTED, self.mitra)
            return original_save(form, *args, **kwargs)

        with patch.object(RepairRequestEditForm, 'save', new=accept_then_save):
            response = self.client.post(reverse('repair:edit', kwargs={'pk': repair.pk}), {
                'item_name': 'Edit terlambat', 'description': 'Tidak boleh tersimpan.',
            })
        self.assertRedirects(response, reverse('repair:detail', kwargs={'pk': repair.pk}))
        repair.refresh_from_db()
        self.assertEqual(repair.status, RepairRequest.Status.ACCEPTED)
        self.assertEqual(repair.item_name, 'Ponsel')
        self.assertEqual(repair.status_history.count(), 2)

    def test_cancel_requires_confirmation_post_and_keeps_history(self):
        repair = self.make_request()
        url = reverse('repair:cancel', kwargs={'pk': repair.pk})
        confirmation = self.client.get(url)
        self.assertContains(confirmation, 'Batalkan permintaan ini?')
        self.assertEqual(repair.status_history.count(), 1)
        response = self.client.post(url)
        self.assertRedirects(
            response, reverse('repair:detail', kwargs={'pk': repair.pk}),
            fetch_redirect_response=False,
        )
        repair.refresh_from_db()
        self.assertEqual(repair.status, RepairRequest.Status.CANCELLED)
        event = repair.status_history.order_by('-pk').first()
        self.assertEqual(event.from_status, RepairRequest.Status.PENDING)
        self.assertEqual(event.to_status, RepairRequest.Status.CANCELLED)
        self.assertEqual(event.customer_actor, self.customer)
        self.assertTrue(timezone.is_aware(event.occurred_at))
        self.assertTrue(RepairRequest.objects.filter(pk=repair.pk).exists())
        self.assertContains(self.client.get(reverse('repair:detail', kwargs={'pk': repair.pk})), 'berhasil dibatalkan')
        second = self.client.post(url)
        self.assertRedirects(second, reverse('repair:detail', kwargs={'pk': repair.pk}))
        self.assertEqual(repair.status_history.count(), 2)

    def test_cancel_permissions_and_csrf(self):
        repair = self.make_request()
        url = reverse('repair:cancel', kwargs={'pk': repair.pk})
        self.client.force_login(
            self.other_customer, backend='authentication.backends.CustomerBackend',
        )
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(url).status_code, 404)
        self.client.force_login(self.mitra, backend='authentication.backends.MitraBackend')
        self.assertEqual(self.client.post(url).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.post(url).status_code, 302)
        protected_client = Client(enforce_csrf_checks=True)
        protected_client.force_login(
            self.customer, backend='authentication.backends.CustomerBackend',
        )
        self.assertEqual(protected_client.post(url).status_code, 403)
        self.assertEqual(repair.status_history.count(), 1)

    def test_cancel_handles_competing_acceptance(self):
        repair = self.make_request()
        url = reverse('repair:cancel', kwargs={'pk': repair.pk})
        original_transition = RepairRequest.transition_to

        def accept_then_cancel(instance, status, actor, reason=''):
            if status == RepairRequest.Status.CANCELLED:
                current = RepairRequest.objects.get(pk=repair.pk)
                original_transition(current, RepairRequest.Status.ACCEPTED, self.mitra)
            return original_transition(instance, status, actor, reason=reason)

        with patch.object(RepairRequest, 'transition_to', new=accept_then_cancel):
            response = self.client.post(url)
        self.assertRedirects(response, reverse('repair:detail', kwargs={'pk': repair.pk}))
        repair.refresh_from_db()
        self.assertEqual(repair.status, RepairRequest.Status.ACCEPTED)
        self.assertEqual(
            list(repair.status_history.values_list('to_status', flat=True)),
            [RepairRequest.Status.PENDING, RepairRequest.Status.ACCEPTED],
        )


class MitraDashboardTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create_user(
            username='dashboard-customer', password='test-password',
            nama_lengkap='Pelanggan Daun', no_hp='0811',
        )
        self.mitra = MitraReparasi.objects.create_user(
            username='dashboard-mitra', password='test-password',
            nama_lengkap='Pemilik Bengkel', no_hp='0812',
            nama_usaha='Bengkel Hijau', layanan=[KategoriBarang.GADGET],
            alamat='Jakarta', latitude='-6.200000', longitude='106.816666',
        )
        self.other_mitra = MitraReparasi.objects.create_user(
            username='other-dashboard-mitra', password='test-password',
            nama_lengkap='Mitra Lain', no_hp='0813',
            nama_usaha='Bengkel Lain', layanan=[KategoriBarang.SEPEDA],
            alamat='Depok', latitude='-6.400000', longitude='106.800000',
        )
        self.client.force_login(self.mitra, backend='authentication.backends.MitraBackend')

    def make_request(self, *, mitra=None, category=KategoriBarang.GADGET,
                     name='Ponsel', description='Layar retak.'):
        return RepairRequest.objects.create(
            customer=self.customer, mitra=mitra or self.mitra,
            category=category, item_name=name, description=description,
        )

    def ajax_get(self, params=None):
        return self.client.get(
            reverse('repair:incoming'), params or {},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

    def ajax_post(self, repair, status, reason=''):
        return self.client.post(
            reverse('repair:mitra_transition', args=[repair.pk]),
            {'expected_status': repair.status, 'to_status': status, 'reason': reason},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

    def test_dashboard_requires_mitra_and_shows_only_assigned_incoming(self):
        own = self.make_request(name='Barang Saya')
        other = self.make_request(mitra=self.other_mitra, name='Barang Mitra Lain')
        response = self.client.get(reverse('repair:incoming'))
        self.assertContains(response, own.item_name)
        self.assertContains(response, self.customer.nama_lengkap)
        self.assertNotContains(response, other.item_name)
        self.assertEqual(response.context['counts']['incoming'], 1)
        self.assertContains(response, 'name="group"')
        detail = self.client.get(reverse('repair:detail', args=[own.pk]))
        self.assertContains(detail, 'Ruang kerja mitra')
        self.assertContains(detail, f'href="{reverse("repair:incoming")}"')
        self.client.force_login(self.customer, backend='authentication.backends.CustomerBackend')
        self.assertEqual(self.client.get(reverse('repair:incoming')).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(reverse('repair:incoming')).status_code, 302)

    def test_dashboard_groups_filters_search_and_empty_result(self):
        pending = self.make_request(name='Ponsel Baru', description='Baterai panas')
        active = self.make_request(category=KategoriBarang.SEPEDA, name='Sepeda Kota')
        active.transition_to(RepairRequest.Status.ACCEPTED, self.mitra)
        finished = self.make_request(name='Radio Lama')
        finished.transition_to(RepairRequest.Status.REJECTED, self.mitra, reason='Komponen habis')
        self.make_request(mitra=self.other_mitra, name='Rahasia')

        active_response = self.client.get(reverse('repair:incoming'), {'group': 'active'})
        self.assertContains(active_response, active.item_name)
        self.assertNotContains(active_response, pending.item_name)
        self.assertEqual(active_response.context['counts'], {'incoming': 1, 'active': 1, 'history': 1})
        history = self.client.get(reverse('repair:incoming'), {'group': 'history', 'status': 'rejected'})
        self.assertContains(history, finished.item_name)
        self.assertNotContains(history, active.item_name)
        combined = self.client.get(reverse('repair:incoming'), {
            'group': 'active', 'category': KategoriBarang.SEPEDA,
            'status': 'accepted', 'q': 'kota',
        })
        self.assertEqual([repair.pk for repair in combined.context['repairs']], [active.pk])
        customer_search = self.client.get(reverse('repair:incoming'), {'q': 'pelanggan daun'})
        self.assertEqual([repair.pk for repair in customer_search.context['repairs']], [pending.pk])
        issue_search = self.client.get(reverse('repair:incoming'), {'q': 'baterai panas'})
        self.assertEqual([repair.pk for repair in issue_search.context['repairs']], [pending.pk])
        empty = self.client.get(reverse('repair:incoming'), {'q': 'tidak ada'})
        self.assertContains(empty, 'Tidak ada hasil yang cocok')
        self.assertEqual(empty.context['result_count'], 0)

    def test_ajax_get_returns_only_results_partial_and_regular_get_keeps_filters(self):
        self.make_request(name='Tablet')
        partial = self.ajax_get({'group': 'incoming', 'q': 'tablet'})
        self.assertEqual(partial.status_code, 200)
        self.assertTemplateUsed(partial, 'repair/_mitra_results.html')
        self.assertContains(partial, 'Tablet')
        self.assertNotContains(partial, '<html')
        self.assertContains(partial, 'data-result-count="1"')
        regular = self.client.get(reverse('repair:incoming'), {'q': 'tablet'})
        self.assertTemplateUsed(regular, 'repair/mitra_dashboard.html')
        self.assertContains(regular, 'value="tablet"')

    def test_valid_ajax_transitions_write_one_event_and_return_authoritative_results(self):
        scenarios = [
            ([], RepairRequest.Status.ACCEPTED, ''),
            ([], RepairRequest.Status.REJECTED, 'Suku cadang tidak tersedia.'),
            ([RepairRequest.Status.ACCEPTED], RepairRequest.Status.IN_PROGRESS, ''),
            ([RepairRequest.Status.ACCEPTED], RepairRequest.Status.UNABLE_TO_REPAIR, 'Mesin rusak berat.'),
            ([RepairRequest.Status.ACCEPTED, RepairRequest.Status.IN_PROGRESS], RepairRequest.Status.COMPLETED, ''),
            ([RepairRequest.Status.ACCEPTED, RepairRequest.Status.IN_PROGRESS], RepairRequest.Status.UNABLE_TO_REPAIR, 'Tidak aman diperbaiki.'),
        ]
        for index, (before, target, reason) in enumerate(scenarios):
            with self.subTest(target=target, before=before):
                repair = self.make_request(name=f'Barang {index}')
                for status in before:
                    repair.transition_to(status, self.mitra)
                count = repair.status_history.count()
                response = self.ajax_post(repair, target, reason)
                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertTrue(payload['ok'])
                self.assertEqual(payload['request']['status'], target)
                self.assertEqual(payload['event']['reason'], reason)
                self.assertEqual(payload['event']['actor'], self.mitra.nama_usaha)
                self.assertIn('results_html', payload)
                repair.refresh_from_db()
                self.assertEqual(repair.status, target)
                self.assertEqual(repair.status_history.count(), count + 1)
                event = repair.status_history.order_by('-pk').first()
                self.assertEqual(event.mitra_actor, self.mitra)
                self.assertTrue(timezone.is_aware(event.occurred_at))
                self.assertEqual(repair.is_successful, target == RepairRequest.Status.COMPLETED)

    def test_ajax_action_refreshes_active_card_and_group_counts(self):
        repair = self.make_request()
        repair.transition_to(RepairRequest.Status.ACCEPTED, self.mitra)
        response = self.client.post(
            reverse('repair:mitra_transition', args=[repair.pk]) + '?group=active',
            {'expected_status': RepairRequest.Status.ACCEPTED,
             'to_status': RepairRequest.Status.IN_PROGRESS},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['counts'], {'incoming': 0, 'active': 1, 'history': 0})
        self.assertIn('In Progress', payload['results_html'])
        self.assertIn('Tandai selesai', payload['results_html'])
        self.assertNotIn('Mulai reparasi', payload['results_html'])

    def test_terminal_history_has_no_action_forms(self):
        repair = self.make_request()
        repair.transition_to(RepairRequest.Status.REJECTED, self.mitra, 'Tidak tersedia')
        response = self.client.get(reverse('repair:incoming'), {'group': 'history'})
        self.assertContains(response, repair.item_name)
        self.assertNotContains(response, 'data-mitra-action')

    def test_reason_is_required_for_rejection_and_unable_outcome(self):
        pending = self.make_request()
        rejected = self.ajax_post(pending, RepairRequest.Status.REJECTED, '   ')
        self.assertEqual(rejected.status_code, 400)
        self.assertIn('reason', rejected.json()['errors'])
        self.assertEqual(pending.status_history.count(), 1)
        pending.transition_to(RepairRequest.Status.ACCEPTED, self.mitra)
        unable = self.ajax_post(pending, RepairRequest.Status.UNABLE_TO_REPAIR)
        self.assertEqual(unable.status_code, 400)
        self.assertEqual(pending.status_history.count(), 2)

    def test_invalid_repeated_and_stale_actions_return_correct_codes(self):
        repair = self.make_request()
        invalid = self.ajax_post(repair, 'completed')
        self.assertEqual(invalid.status_code, 400)
        unknown = self.ajax_post(repair, 'imaginary')
        self.assertEqual(unknown.status_code, 400)
        self.assertEqual(self.ajax_post(repair, RepairRequest.Status.ACCEPTED).status_code, 200)
        repeated = self.ajax_post(repair, RepairRequest.Status.ACCEPTED)
        self.assertEqual(repeated.status_code, 409)
        self.assertFalse(repeated.json()['ok'])
        self.assertEqual(repair.status_history.count(), 2)

    def test_competing_change_is_reported_as_conflict(self):
        repair = self.make_request()
        original_transition = RepairRequest.transition_to

        def reject_then_accept(instance, status, actor, reason=''):
            current = RepairRequest.objects.get(pk=repair.pk)
            original_transition(current, RepairRequest.Status.REJECTED, self.mitra, 'Tidak tersedia')
            return original_transition(instance, status, actor, reason=reason)

        with patch.object(RepairRequest, 'transition_to', new=reject_then_accept):
            response = self.ajax_post(repair, RepairRequest.Status.ACCEPTED)
        self.assertEqual(response.status_code, 409)
        repair.refresh_from_db()
        self.assertEqual(repair.status, RepairRequest.Status.REJECTED)
        self.assertEqual(repair.status_history.count(), 2)

    def test_unassigned_mitra_and_customer_cannot_transition(self):
        repair = self.make_request()
        self.client.force_login(self.other_mitra, backend='authentication.backends.MitraBackend')
        self.assertEqual(self.ajax_post(repair, RepairRequest.Status.ACCEPTED).status_code, 404)
        self.client.force_login(self.customer, backend='authentication.backends.CustomerBackend')
        self.assertEqual(self.ajax_post(repair, RepairRequest.Status.ACCEPTED).status_code, 403)
        self.client.logout()
        self.assertEqual(self.ajax_post(repair, RepairRequest.Status.ACCEPTED).status_code, 302)
        self.assertEqual(repair.status_history.count(), 1)

    def test_standard_post_redirects_and_customer_sees_reason(self):
        repair = self.make_request()
        response = self.client.post(
            reverse('repair:mitra_transition', args=[repair.pk]),
            {'expected_status': RepairRequest.Status.PENDING,
             'to_status': RepairRequest.Status.REJECTED, 'reason': 'Tidak ada suku cadang.'},
        )
        self.assertRedirects(response, reverse('repair:incoming'))
        self.client.force_login(self.customer, backend='authentication.backends.CustomerBackend')
        detail = self.client.get(reverse('repair:detail', args=[repair.pk]))
        self.assertContains(detail, 'Tidak ada suku cadang.')
        self.assertContains(detail, 'Bengkel Hijau')

    def test_standard_post_invalid_reason_redirects_without_mutation(self):
        repair = self.make_request()
        response = self.client.post(
            reverse('repair:mitra_transition', args=[repair.pk]),
            {'expected_status': RepairRequest.Status.PENDING,
             'to_status': RepairRequest.Status.REJECTED, 'reason': ''},
        )
        self.assertRedirects(response, reverse('repair:incoming'))
        repair.refresh_from_db()
        self.assertEqual(repair.status, RepairRequest.Status.PENDING)
        self.assertEqual(repair.status_history.count(), 1)

    def test_transition_requires_post_and_csrf(self):
        repair = self.make_request()
        url = reverse('repair:mitra_transition', args=[repair.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        protected = Client(enforce_csrf_checks=True)
        protected.force_login(self.mitra, backend='authentication.backends.MitraBackend')
        self.assertEqual(protected.post(url, {'to_status': 'accepted'}).status_code, 403)
        protected.get(reverse('repair:incoming'))
        token = protected.cookies['csrftoken'].value
        valid = protected.post(
            url, {'expected_status': RepairRequest.Status.PENDING, 'to_status': 'accepted'},
            HTTP_X_CSRFTOKEN=token, HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(valid.status_code, 200)
        self.assertEqual(repair.status_history.count(), 2)
