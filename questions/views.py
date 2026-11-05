from django.http import Http404
from django.shortcuts import render

from .demo_data import ANSWERS, QUESTIONS


def index(request):
    questions = sorted(QUESTIONS, key=lambda question: question['created_at'], reverse=True)
    return render(request, 'questions/index.html', {'questions': questions})


def hot(request):
    questions = sorted(QUESTIONS, key=lambda question: question['rating'], reverse=True)
    return render(request, 'questions/hot.html', {'questions': questions})


def tag(request, slug):
    questions = [
        question for question in QUESTIONS
        if any(tag.lower() == slug for tag in question['tags'])
    ]
    return render(request, 'questions/tag.html', {'questions': questions, 'tag': slug})


def detail(request, pk):
    question = next((question for question in QUESTIONS if question['id'] == pk), None)
    if question is None:
        raise Http404
    return render(request, 'questions/question.html', {
        'question': question,
        'answers': ANSWERS.get(pk, []),
    })


def ask(request):
    return render(request, 'questions/ask.html')
