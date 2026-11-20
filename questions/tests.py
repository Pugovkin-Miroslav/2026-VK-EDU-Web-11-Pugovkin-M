from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import resolve

from .models import Answer, AnswerLike, Question, QuestionLike, Tag


class QuestionModelsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model().objects
        cls.author = users.create_user(username='author')
        cls.reader = users.create_user(username='reader')
        cls.question = Question.objects.create(
            title='Как работает Django ORM?', text='Пример вопроса.', author=cls.author,
        )
        cls.answer = Answer.objects.create(
            text='ORM преобразует операции с моделями в запросы к БД.',
            question=cls.question,
            author=cls.reader,
        )

    def test_question_links_to_detail_answers_and_tags(self):
        tag = Tag.objects.create(name='Django', slug='django')
        self.question.tags.add(tag)

        match = resolve(self.question.get_absolute_url())
        self.assertEqual(match.view_name, 'questions:detail')
        self.assertEqual(match.kwargs, {'pk': self.question.pk})
        self.assertEqual(list(self.question.answers.all()), [self.answer])
        self.assertEqual(list(tag.questions.all()), [self.question])

    def test_tag_rejects_a_slug_that_cannot_be_used_in_its_url(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Tag.objects.create(name='Джанго', slug='джанго')

    def test_question_like_is_unique_per_user_and_question(self):
        other_question = Question.objects.create(
            title='Другой вопрос', text='Описание.', author=self.author,
        )
        QuestionLike.objects.create(user=self.reader, question=self.question)
        QuestionLike.objects.create(user=self.author, question=self.question)
        QuestionLike.objects.create(user=self.reader, question=other_question)

        with self.assertRaises(IntegrityError), transaction.atomic():
            QuestionLike.objects.create(user=self.reader, question=self.question)

    def test_answer_like_is_unique_per_user_and_answer(self):
        other_answer = Answer.objects.create(
            text='Другой ответ.', question=self.question, author=self.author,
        )
        AnswerLike.objects.create(user=self.reader, answer=self.answer)
        AnswerLike.objects.create(user=self.author, answer=self.answer)
        AnswerLike.objects.create(user=self.reader, answer=other_answer)

        with self.assertRaises(IntegrityError), transaction.atomic():
            AnswerLike.objects.create(user=self.reader, answer=self.answer)
