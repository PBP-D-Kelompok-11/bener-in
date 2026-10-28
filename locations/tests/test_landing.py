from django.urls import reverse

from .base import LocationsTestCase


class LandingPageMitraScriptTests(LocationsTestCase):
    def test_landing_page_loads_mitra_script_before_home_script(self):
        html = self.client.get(reverse('landing_page')).content.decode()
        mitra = html.index('js/home-mitra.js')
        home = html.index('js/home.js')
        self.assertLess(mitra, home)  # harus menangkap peta sebelum home.js membuatnya

    def test_script_receives_api_and_login_urls(self):
        html = self.client.get(reverse('landing_page')).content.decode()
        self.assertIn(f'data-mitra-url="{reverse("locations:api_mitra")}"', html)
        self.assertIn(f'data-login-url="{reverse("authentication:login")}"', html)


class RegisterMitraAddressScriptTests(LocationsTestCase):
    def setUp(self):
        super().setUp()
        self.html = self.client.get(reverse('authentication:register_mitra')).content.decode()

    def test_address_script_loads_between_leaflet_and_inline_map_script(self):
        leaflet = self.html.index('leaflet@1.9.4/dist/leaflet.js')
        address = self.html.index('js/register-mitra-address.js')
        inline = self.html.index("L.map('pick-map')")
        self.assertLess(leaflet, address)  # butuh L.Map.addInitHook
        self.assertLess(address, inline)   # harus menangkap peta sebelum dibuat

    def test_script_receives_reverse_url(self):
        self.assertIn(f'data-reverse-url="{reverse("locations:api_reverse")}"', self.html)

    def test_form_still_has_address_field_and_hidden_coordinates(self):
        for field_id in ('id_alamat', 'id_latitude', 'id_longitude'):
            self.assertIn(f'id="{field_id}"', self.html)
