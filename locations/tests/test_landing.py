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
