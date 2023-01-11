from django.test import TestCase, Client
from ..models import Post, User, Group
from http import HTTPStatus
from django.urls import reverse
from django.core.cache import cache


class StaticURLTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.author = User.objects.create_user(username='author')
        cls.not_author = User.objects.create_user(username='test_client')
        cls.group = Group.objects.create(
            title='test_title',
            slug='test_slug'
        )
        cls.post = Post.objects.create(
            text='test text',
            author=cls.author,
            group=cls.group
        )
        cls.post_id = cls.post.id
        cls.template_url_names = {
            reverse('posts:index'): ['posts/index.html', HTTPStatus.OK],
            reverse('posts:group_list', kwargs={'slug': cls.group.slug}):
                ['posts/group_list.html', HTTPStatus.OK],
            reverse('posts:profile', kwargs={'username': cls.author.username}):
                ['posts/profile.html', HTTPStatus.OK],
            reverse('posts:post_detail', kwargs={'post_id': cls.post.pk}):
                ['posts/post_detail.html', HTTPStatus.OK],
            reverse('posts:post_create'):
                ['posts/post_create.html', HTTPStatus.FOUND],
            reverse('posts:post_edit', kwargs={'post_id': cls.post.pk}):
                ['posts/post_create.html', HTTPStatus.FOUND],
        }
        cls.url_names_https_status_auth = {
            '/': HTTPStatus.OK,
            f'/group/{cls.group.slug}/': HTTPStatus.OK,
            f'/profile/{cls.author.username}': HTTPStatus.OK,
            '/unexciting_page/': HTTPStatus.NOT_FOUND
        }

    def setUp(self) -> None:
        self.guest_client = Client()
        self.authorized_client = Client()
        self.authorized_client.force_login(self.not_author)
        self.authorized_client_author = Client()
        self.authorized_client_author.force_login(self.author)
        self.authorized_client_not_author = Client()
        self.authorized_client_not_author.force_login(
            StaticURLTests.not_author
        )
        cache.clear()

    def test_homepage(self):
        response = self.guest_client.get('/')
        self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_urls_guest(self):
        """Страницы недоступны неавторизованному юзеру"""
        for address, template in self.template_url_names.items():
            with self.subTest(address=address):
                response = self.guest_client.get(address)
                self.assertEqual(response.status_code, template[1])

    def test_url_avaible_auth_user(self):
        """Страницы из url httpstatus доступны
        авторизованному пользователю"""
        for address, httpstatus in self.url_names_https_status_auth.items():
            with self.subTest(adress=address):
                response = self.authorized_client.get(address, follow=True)
                self.assertEqual(response.status_code, httpstatus)

    def test_pages_uses_correct_templates(self):
        """url-адрес использует соответсвующий шаблон"""
        for address, template in self.template_url_names.items():
            with self.subTest(address=address):
                response = self.authorized_client_author.get(
                    address, follow=True)
                self.assertTemplateUsed(response, template[0])

    def test_redirect_anonymous(self):
        """Перенаправление незарегистрированного
        пользователя на страницу авторизации из url redirect"""
        self.assertRedirects(
            self.guest_client.get(f'/posts/{self.post.id}/edit/'),
            '/auth/login/' + '?next=' + f'/posts/{self.post.id}/edit/')
        self.assertRedirects(
            self.guest_client.get('/create/'),
            '/auth/login/' + '?next=' + '/create/')

    def test_post_edit_redirect_auth_user_no_author(self):
        """Страница post/<int>/edit/ переадресует авторизованного НЕавтора"""
        response = self.authorized_client.get(reverse('posts:post_edit',
                                                      args=(self.post.id,)))
        self.assertRedirects(response, reverse('posts:post_detail',
                                               args=(self.post.id,)))
