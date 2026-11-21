from django.urls import path

from . import views
from .models import Answer, Question

app_name = 'questions'

urlpatterns = [
    path('', views.index, name='index'),
    path('hot/', views.hot, name='hot'),
    path('tag/<slug:slug>/', views.tag, name='tag'),
    path('question/<int:pk>/', views.detail, name='detail'),
    path('ask/', views.ask, name='ask'),
    path('ajax/vote/question/', views.vote, {'target_model': Question}, name='ajax_vote_question'),
    path('ajax/vote/answer/', views.vote, {'target_model': Answer}, name='ajax_vote_answer'),
    path('ajax/answer/correct/', views.mark_correct_answer, name='ajax_mark_correct_answer'),
]
