from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.debug import sensitive_post_parameters

from .forms import ProfileForm, SignupForm


@sensitive_post_parameters('password1', 'password2')
def signup(request):
    form = SignupForm(request.POST if request.method == 'POST' else None)
    if form.is_valid():
        user = form.save()
        login(request, user)
        return redirect('questions:index')
    return render(request, 'core/signup.html', {'form': form})


@login_required
def profile(request):
    if request.method == 'POST':
        form = ProfileForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            form.save()
            return redirect('core:profile')
    else:
        form = ProfileForm(user=request.user)
    return render(request, 'core/profile.html', {'form': form})
