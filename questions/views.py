from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.csrf import csrf_failure as default_csrf_failure

from .forms import AnswerForm, CorrectAnswerForm, QuestionForm, VoteForm
from .models import Answer, Question, Tag
from .pagination import pagination_context


def _render_list(request, template, questions, **context):
    return render(request, template, {**pagination_context(questions, request), **context})


def index(request):
    return _render_list(request, 'questions/index.html', Question.objects.newest(request.user))


def hot(request):
    return _render_list(request, 'questions/hot.html', Question.objects.popular(request.user))


def tag(request, slug):
    selected_tag = get_object_or_404(Tag, slug=slug)
    questions = Question.objects.for_tag(selected_tag, request.user)
    return _render_list(request, 'questions/tag.html', questions, tag=selected_tag)


def _render_question(request, question, form):
    context = pagination_context(Answer.objects.for_question(question, request.user), request)
    return render(request, 'questions/question.html', {'question': question, 'form': form, **context})


@login_required
def _post_answer(request, question):
    form = AnswerForm(request.POST)
    if form.is_valid():
        return redirect(form.save(question=question, author=request.user))
    return _render_question(request, question, form)


def detail(request, pk):
    question = get_object_or_404(Question.objects.with_card_data(request.user), pk=pk)
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


def _ajax_form_response(request, form_class, *, auth_message, invalid_message, **save_kwargs):
    if request.method != 'POST':
        return JsonResponse({'error': 'Допустим только метод POST.'}, status=405, headers={'Allow': 'POST'})
    if not request.user.is_authenticated:
        return JsonResponse({'error': auth_message}, status=401)

    form = form_class(request.POST)
    if not form.is_valid():
        return JsonResponse({'error': invalid_message}, status=400)

    try:
        result = form.save(user=request.user, **save_kwargs)
    except ValidationError as error:
        status = {'not_found': 404, 'permission_denied': 403, 'conflict': 409}.get(error.code, 400)
        return JsonResponse({'error': error.message}, status=status)
    return JsonResponse(result)


def vote(request, target_model):
    return _ajax_form_response(
        request, VoteForm,
        auth_message='Войдите, чтобы голосовать.',
        invalid_message='Некорректные данные голосования.',
        target_model=target_model,
    )


def mark_correct_answer(request):
    return _ajax_form_response(
        request, CorrectAnswerForm,
        auth_message='Войдите, чтобы отметить правильный ответ.',
        invalid_message='Некорректные данные ответа.',
    )


def csrf_failure(request, reason=''):
    match = request.resolver_match
    if match and match.namespace == 'questions' and (match.url_name or '').startswith('ajax_'):
        return JsonResponse({'error': 'Ошибка проверки CSRF. Обновите страницу и повторите попытку.'}, status=403)
    return default_csrf_failure(request, reason=reason)
