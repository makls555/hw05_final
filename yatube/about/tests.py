from http import HTTPStatus
from django.test import TestCase, Client


class StaticURLTests(TestCase):
    def setUp(self):
        """Устанавливаем данные для тестирования."""
        self.guest_client = Client()

    def test_urls_about_correct_template(self):
        """url-адрес использует соответсвующий шаблон"""
        templates_urls_name = {
            'about/author.html': '/about/author/',
            'about/tech.html': '/about/tech/'
        }
        for template, address in templates_urls_name.items():
            with self.subTest(address=address):
                response = self.guest_client.get(address, follow=True)
                self.assertTemplateUsed(response, template)

    def tests_urls_about_avaible(self):
        """Страницы из url httpstatus доступны всем пользователям."""
        urls_names_https_status = {
            '/about/author/': HTTPStatus.OK,
            '/about/tech/': HTTPStatus.OK
        }
        for address, httpstatus in urls_names_https_status.items():
            with self.subTest(address=address):
                response = self.guest_client.get(address)
                self.assertEqual(response.status_code, httpstatus)
