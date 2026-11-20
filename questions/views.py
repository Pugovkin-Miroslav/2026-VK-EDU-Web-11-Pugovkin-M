from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .forms import AnswerForm, QuestionForm
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


def _render_question(request, question, form):
    context = pagination_context(Answer.objects.for_question(question), request)
    return render(request, 'questions/question.html', {'question': question, 'form': form, **context})


@login_required
def _post_answer(request, question):
    form = AnswerForm(request.POST)
    if form.is_valid():
        return redirect(form.save(question=question, author=request.user))
    return _render_question(request, question, form)


def detail(request, pk):
    question = get_object_or_404(Question.objects.with_card_data(), pk=pk)
    if request.method == 'POST':
        return _post_answer(request, question)
    return _render_question(request, question, AnswerForm())


@login_required
def ask(request):
    form = QuestionForm(
        request.POST if request.method == 'POST' else None,
        author=request.user,
    )
    if form.is_valid():
        return redirect(form.save())
    return render(request, 'questions/ask.html', {'form': form})
