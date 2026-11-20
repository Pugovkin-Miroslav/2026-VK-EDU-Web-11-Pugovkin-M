from django.shortcuts import render


def signup(request):
    return render(request, 'core/signup.html')


def profile(request):
    return render(request, 'core/profile.html')
