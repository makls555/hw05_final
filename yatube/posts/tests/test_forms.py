from django.urls import reverse
from ..models import Group, Post, User, Comment
import shutil
import tempfile
from django.conf import settings
from django.test import Client, TestCase, override_settings
from django.core.files.uploadedfile import SimpleUploadedFile

TEMP_MEDIA_ROOT = tempfile.mkdtemp(dir=settings.BASE_DIR)


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class PostFormTests(TestCase):
    @classmethod
    def setUpClass(cls):
        """Создаем автора и две группы."""
        super().setUpClass()
        cls.author = User.objects.create_user(username='author')
        cls.group_1 = Group.objects.create(
            title='Первая тестовая группа',
            slug='group_test_1'
        )
        cls.group_2 = Group.objects.create(
            title='Вторая тестовая группа',
            slug='group_test_2'
        )
        cls.gif = (
            b'\x47\x49\x46\x38\x39\x61\x02\x00'
            b'\x01\x00\x80\x00\x00\x00\x00\x00'
            b'\xFF\xFF\xFF\x21\xF9\x04\x00\x00'
            b'\x00\x00\x00\x2C\x00\x00\x00\x00'
            b'\x02\x00\x01\x00\x00\x02\x02\x0C'
            b'\x0A\x00\x3B'
        )

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        """Создаем клиента и пост."""
        self.authorized_client = Client()
        self.authorized_client.force_login(self.author)
        self.post = Post.objects.create(
            text='Тестовый пост',
            author=self.author,
            group=self.group_1)

    def test_create_post_form(self):
        """При отправке формы создается новый пост в базе данных.
        После создания происходит редирект на профиль автора.
        """
        post_count = Post.objects.all().count()
        uploaded = SimpleUploadedFile(
            name='small.gif',
            content=self.gif,
            content_type='image/gif'
        )
        form_data = {
            'text': 'Еще один пост',
            'group': self.group_1.id,
            'image': uploaded
        }
        response = self.authorized_client.post(
            reverse('posts:post_create'),
            data=form_data,
            follow=True
        )
        self.assertRedirects(
            response,
            reverse('posts:profile', kwargs={'username': self.author.username})
        )
        self.assertEqual(
            Post.objects.all().count(),
            post_count + 1,
            'Пост не сохранен в базу данных!'
        )
        self.assertTrue(
            Post.objects.filter(
                text='Тестовый пост',
                group=self.group_1
            ).exists())
        self.assertTrue(
            Post.objects.filter(
                text='Тестовый пост',
                author=self.author
            ).exists())
        self.assertEqual(response.context['page_obj'].object_list[0].image,
                         'posts/small.gif')

    def test_edit_post_form(self):
        """При отправке формы изменяется пост в базе данных.
        После редактирования происходит редирект на карточку поста.
        """
        posts_count = Post.objects.count()
        form_data = {
            'text': 'Измененный текст поста',
            'group': self.group_2.id
        }
        response = self.authorized_client.post(
            reverse('posts:post_edit', args=[self.post.id]),
            data=form_data,
            follow=True)
        modified_post = Post.objects.get(id=self.post.id)
        self.assertRedirects(response, reverse('posts:post_detail', args=(1,)))
        self.assertEqual(Post.objects.count(), posts_count)
        self.assertNotEqual(
            modified_post.text,
            self.post.text,
            'Текст поста не изменился!'
        )
        self.assertNotEqual(
            modified_post.group,
            self.post.group,
            'Группа у поста не изменилась!'
        )
        self.assertEqual(modified_post.group.title,
                         'Вторая тестовая группа')

    def test_comment_can_authorized_user(self):
        """Комментировать может только авторизованный пользователь."""
        form_data = {
            'text': 'Новый комментарий',
        }
        response = self.authorized_client.post(
            reverse((
                'posts:add_comment'), kwargs={'post_id': f'{self.post.id}'}),
            data=form_data,
            follow=True
        )
        self.assertRedirects(response, reverse((
            'posts:post_detail'), kwargs={'post_id': f'{self.post.id}'}))
        self.assertTrue(
            Comment.objects.filter(text='Новый комментарий').exists()
        )

    def test_comment_show_up(self):
        """Комментарий появляется на странице поста"""
        comments_count = Comment.objects.count()
        form_data = {
            'text': 'Новый комментарий',
        }
        response = self.authorized_client.post(
            reverse((
                'posts:add_comment'), kwargs={'post_id': f'{self.post.id}'}),
            data=form_data,
            follow=True
        )
        self.assertRedirects(response, reverse((
            'posts:post_detail'), kwargs={'post_id': f'{self.post.id}'}))
        self.assertEqual(Comment.objects.count(), comments_count + 1)
