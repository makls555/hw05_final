from django import forms
from django.test import Client, TestCase, override_settings
from django.http.response import HttpResponse
from django.urls import reverse
from ..models import Group, Post, User, Follow
from django.conf import settings
import tempfile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.cache import cache
import shutil
from ..views import SELECT_LIMIT

POSTS_PER_PAGE = 10
TEMP_MEDIA_ROOT = tempfile.mkdtemp(dir=settings.BASE_DIR)


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class PostViewTests(TestCase):
    @classmethod
    def setUpClass(cls):
        """Создаем двух авторов и две группы."""
        super().setUpClass()
        cls.author_1 = User.objects.create_user(username='author_1')
        cls.author_2 = User.objects.create_user(username='author_2')
        cls.group_1 = Group.objects.create(
            title='Группа_1',
            slug='group_1'
        )
        cls.gif = (
            b'\x47\x49\x46\x38\x39\x61\x02\x00'
            b'\x01\x00\x80\x00\x00\x00\x00\x00'
            b'\xFF\xFF\xFF\x21\xF9\x04\x00\x00'
            b'\x00\x00\x00\x2C\x00\x00\x00\x00'
            b'\x02\x00\x01\x00\x00\x02\x02\x0C'
            b'\x0A\x00\x3B'
        )
        cls.uploaded = SimpleUploadedFile(
            name='small.gif',
            content=cls.gif,
            content_type='image/gif'
        )
        cls.group_2 = Group.objects.create(
            title='Группа_2',
            slug='group_2'
        )
        cache.clear()

    def setUp(self):
        """Создаем авторизованных клиентов и несколько постов."""
        self.authorized_client_1 = Client()
        self.authorized_client_1.force_login(self.author_1)
        self.authorized_client_2 = Client()
        self.authorized_client_2.force_login(self.author_2)
        self.post_1 = Post.objects.create(
            text='test_text_1',
            author=self.author_1,
            group=self.group_1
        )
        self.post_2 = Post.objects.create(
            text='test_text_2',
            author=self.author_2,
            group=None
        )
        self.post_3 = Post.objects.create(
            text='test_text_3',
            author=self.author_1,
            group=self.group_2
        )
        cache.clear()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(settings.MEDIA_ROOT, ignore_errors=True)
        super().tearDownClass()

    def test_index_cache(self):
        """Кеширование index.html работает."""
        content = self.authorized_client_1.get(
            reverse('posts:index')).content
        self.post_2.delete()
        content_cached = self.authorized_client_2.get(
            reverse('posts:index')).content
        self.assertEqual(content, content_cached)
        cache.clear()
        content_clear = self.authorized_client_2.get(
            reverse('posts:index')).content
        self.assertNotEqual(content, content_clear)

    def test_pages_uses_correct_template(self):
        """URL-адрес использует соответствующий шаблон."""
        templates_pages_names = {
            reverse('posts:index'): 'posts/index.html',
            reverse('posts:group_list',
                    args=[self.group_1.slug]): 'posts/group_list.html',
            reverse('posts:profile',
                    args=[self.author_1.username]): 'posts/profile.html',
            reverse('posts:post_detail',
                    args=[self.post_1.id]): 'posts/post_detail.html',
            reverse('posts:post_create'): 'posts/post_create.html',
            reverse('posts:post_edit',
                    args=[self.post_1.id]): 'posts/post_create.html'
        }
        for reverse_name, template in templates_pages_names.items():
            with self.subTest(reverse_name=reverse_name):
                response = self.authorized_client_1.get(reverse_name)
                self.assertTemplateUsed(response, template)
        response = self.authorized_client_1.get(reverse('posts:index'))

    def test_home_page_show_correct_context(self):
        """Шаблон index сформирован с правильным контекстом и картинкой."""
        response = self.authorized_client_1.get(reverse('posts:index'))
        posts_from_context = response.context.get('page_obj').object_list
        expected_posts = list(Post.objects.all())
        self.assertEqual(posts_from_context, expected_posts,
                         'Главная страница выводит не все посты!'
                         )
        self.assertEqual(posts_from_context[0].image, self.post_3.image,
                         'Картинка не выводится')

    def test_group_list_page_show_correct_context(self):
        """Шаблон group_list сформирован
         с правильным контекстом и картинкой."""
        response = self.authorized_client_1.get(
            reverse('posts:group_list', args=[self.group_2.slug])
        )
        posts_from_context = response.context.get('page_obj').object_list
        group_from_context = response.context.get('group')
        expected_posts = list(Post.objects.filter(group_id=self.group_2.id))
        self.assertEqual(posts_from_context, expected_posts,
                         'Посты в контексте имеют разное значение поле групп!'
                         )
        self.assertEqual(group_from_context, self.group_2,
                         'Страница группы отличается от группы из контекста!'
                         )
        self.assertEqual(posts_from_context[0].image, self.post_3.image,
                         'Картинка не выводится')

    def test_profile_page_show_correct_context(self):
        """Шаблон profile сформирован
         с правильным контекстом и выводом картинки."""
        response = self.authorized_client_1.get(
            reverse('posts:profile', args=[self.author_1.username])
        )
        posts_from_context = response.context.get('page_obj').object_list
        author_from_context = response.context.get('author')
        expected_posts = list(Post.objects.filter(author_id=self.author_1.id))
        self.assertEqual(posts_from_context, expected_posts,
                         'Посты из контекста принадлежать другому автору!'
                         )
        self.assertEqual(author_from_context, self.author_1,
                         'Автор из контекста не совпадает с профилем!'
                         )
        self.assertEqual(posts_from_context[0].image, self.post_3.image,
                         'Картинка не выводится')

    def test_post_detail_show_correct_context(self):
        """Шаблон post_detail сформирован
        с правильным контекстом и выводом картинки."""
        response = self.authorized_client_1.get(
            reverse('posts:post_detail', args=[self.post_3.id])
        )
        post_from_context = response.context.get('post')
        number_posts_author = response.context.get('post_count')
        expected_number = Post.objects.filter(author=self.author_1).count()
        self.assertEqual(post_from_context, self.post_3,
                         'Пост из контекста не совпадает с ожидаемым!'
                         )
        self.assertEqual(number_posts_author, expected_number,
                         'Количество постов автора из контекста неверно!'
                         )
        self.assertEqual(post_from_context.image, self.post_3.image,
                         'Картинка не выводится')

    def test_create_post_show_correct_context(self):
        """Шаблон create_post сформирован с правильным контекстом."""
        response = self.authorized_client_1.get(reverse('posts:post_create'))
        self._check_correct_form_from_context(response)

    def test_new_post_show_on_different_page(self):
        """Новый пост выводится на главной, в выбранной группе,
        и в профайле автора. Не выводится в других группах.
        """
        form_data = {
            'text': 'new_post',
            'group': self.group_1.id
        }
        url_names_assert_method = {
            reverse('posts:index'): self.assertEqual,
            reverse('posts:group_list',
                    args=[self.group_1.slug]): self.assertEqual,
            reverse('posts:profile',
                    args=[self.author_1.username]): self.assertEqual,
            reverse('posts:group_list',
                    args=[self.group_2.slug]): self.assertNotEqual
        }
        self.authorized_client_1.post(
            reverse('posts:post_create'),
            data=form_data
        )
        new_post = Post.objects.latest('id')
        for address, assert_method in url_names_assert_method.items():
            with self.subTest(address=address):
                response = self.authorized_client_1.get(address, follow=True)
                last_post_on_page = response.context.get('page_obj')[0]
                assert_method(last_post_on_page, new_post)

    def test_post_edit_show_correct_context(self):
        """Шаблон страницы post_edit сформирован с правильным контекстом."""
        response = self.authorized_client_1.get(
            reverse('posts:post_edit', args=[self.post_1.id])
        )
        self._check_correct_form_from_context(response)

    def _check_correct_form_from_context(self, response: HttpResponse) -> None:
        """Проверяем корректность формы передаваемой в контексте."""
        form_fields = {
            'text': forms.fields.CharField,
            'group': forms.fields.ChoiceField
        }
        for value, expected in form_fields.items():
            with self.subTest(value=value):
                form_field = response.context.get('form').fields.get(value)
                self.assertIsInstance(form_field, expected)


class PaginatorViewsTest(TestCase):
    @classmethod
    def setUpClass(cls):
        """Создаем автора и группу."""
        super().setUpClass()
        cls.author = User.objects.create_user(username='author_1')
        cls.group = Group.objects.create(
            title='Тестовая группа',
            slug='group_test'
        )
        cache.clear()

    def setUp(self):
        """Создаем клиента и 15 постов."""
        self.client = Client()
        self.number_create_posts = 15
        posts = [Post(text=f'test_text_{i}',
                      author=self.author,
                      group=self.group)
                 for i in range(self.number_create_posts)]
        self.posts = Post.objects.bulk_create(posts)
        self.second_page = Post.objects.count() % SELECT_LIMIT

    def test_pages_uses_correct_template(self):
        """URL-адрес использует соответствующий шаблон."""
        templates_page_number = {
            reverse('posts:index'): SELECT_LIMIT,
            reverse('posts:index') + '?page=2': self.second_page,
            reverse(
                'posts:group_list', kwargs={'slug': 'group_test'}
            ): SELECT_LIMIT,
            reverse(
                'posts:group_list', kwargs={'slug': 'group_test'}
            ) + '?page=2': self.second_page,
            reverse(
                'posts:profile', kwargs={'username': self.author.username}
            ): SELECT_LIMIT,
            reverse(
                'posts:profile', kwargs={'username': self.author.username}
            ) + '?page=2': self.second_page
        }
        for reverse_name, page_number in templates_page_number.items():
            with self.subTest(reverse_name=reverse_name):
                response = self.client.get(reverse_name)
                self.assertEqual(
                    len(response.context['page_obj']), page_number)


class FollowViewsTest(TestCase):
    def setUp(self):
        self.follower = User.objects.create_user(username='Follower')
        self.authorized_client = Client()
        self.authorized_client.force_login(self.follower)
        self.author = User.objects.create_user(username='author')
        self.post_author = Post.objects.create(
            text='текст автора',
            author=self.author,
        )

    def test_follow_author(self):
        follow_count = Follow.objects.count()
        response = self.authorized_client.get(
            reverse('posts:profile_follow', args={self.author}))
        self.assertEqual(Follow.objects.count(), follow_count + 1)
        last_follow = Follow.objects.latest('id')
        self.assertEqual(last_follow.author, self.author)
        self.assertEqual(last_follow.user, self.follower)
        self.assertRedirects(response, reverse(
            'posts:profile', args={self.author}))

    def test_unfollow_author(self):
        follow_count = Follow.objects.count()
        self.authorized_client.get(
            reverse('posts:profile_follow', args={self.author}))
        response = self.authorized_client.get(
            reverse('posts:profile_unfollow', args={self.author}))
        self.assertRedirects(response, reverse(
            'posts:profile', args={self.author}))
        self.assertEqual(Follow.objects.count(), follow_count)

    def test_new_post_follow(self):
        self.authorized_client.get(
            reverse('posts:profile_follow', args={self.author}))
        response = self.authorized_client.get(
            reverse('posts:follow_index'))
        post_follow = response.context['page_obj'][0]
        self.assertEqual(post_follow, self.post_author)

    def test_new_post_unfollow(self):
        new_author = User.objects.create_user(username='new_author')
        self.authorized_client.force_login(new_author)
        Post.objects.create(
            text='новый текст автора',
            author=new_author,
        )
        response = self.authorized_client.get(
            reverse('posts:follow_index'))
        self.assertEqual(len(response.context['page_obj']), 0)
