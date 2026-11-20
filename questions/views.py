from django.shortcuts import get_object_or_404, render

from .models import Answer, Question, Tag
from .pagination import pagination_context


def _render_list(request, template, questions, **context):
    return render(request, template, {**pagination_context(questions, request), **context})


def index(request):
    return _render_list(request, 'questions/index.html', Question.objects.newest())


def hot(request):
    return _render_list(request, 'questions/hot.html', Question.objects.popular())


def tag(request, slug):
    selected_tag = get_object_or_404(Tag, slug=slug)
    questions = Question.objects.for_tag(selected_tag)
    return _render_list(request, 'questions/tag.html', questions, tag=selected_tag)


def detail(request, pk):
    question = get_object_or_404(Question.objects.with_card_data(), pk=pk)
    context = pagination_context(Answer.objects.for_question(question), request)
    return render(request, 'questions/question.html', {'question': question, **context})


def ask(request):
    return render(request, 'questions/ask.html')
