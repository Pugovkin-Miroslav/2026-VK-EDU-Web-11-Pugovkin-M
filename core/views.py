from django.contrib.auth import login
from django.shortcuts import redirect, render
from django.views.decorators.debug import sensitive_post_parameters

from .forms import SignupForm


@sensitive_post_parameters('password1', 'password2')
def signup(request):
    form = SignupForm(request.POST if request.method == 'POST' else None)
    if form.is_valid():
        user = form.save()
        login(request, user)
        return redirect('questions:index')
    return render(request, 'core/signup.html', {'form': form})


def profile(request):
    return render(request, 'core/profile.html')
