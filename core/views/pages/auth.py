"""Authentication and profile page handlers."""

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from core.forms import LoginForm, PreferenceForm, RegisterForm, UserProfileForm
from core.models import UserPreference

from ..shared.http import consume_login_account_rate_limit, consume_rate_limit
from ..shared.messages import (
    AUTH_LOGIN_RATE_LIMIT,
    AUTH_LOGIN_SUCCESS,
    AUTH_LOGOUT_INFO,
    AUTH_REGISTER_RATE_LIMIT,
    AUTH_REGISTER_SUCCESS,
    PROFILE_SAVE_SUCCESS,
)
from ..shared.page_content import PROFILE_HERO_BADGES
from ..shared.panels import build_profile_sidebar_panels

__all__ = ['login_page', 'logout_page', 'profile_page', 'register_page']


def login_page(request):
    if request.user.is_authenticated:
        return redirect('web-home')

    next_url = (request.POST.get('next') or request.GET.get('next') or '').strip()

    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        # Both the per-IP bucket and the per-account bucket must allow the attempt.
        if not consume_rate_limit(request, 'login') or not consume_login_account_rate_limit(
            request,
            request.POST.get('username', ''),
        ):
            messages.error(request, AUTH_LOGIN_RATE_LIMIT)
            return render(request, 'core/pages/auth/login.html', {'form': form, 'next_url': next_url})
        if form.is_valid():
            login(request, form.get_user())
            messages.success(request, AUTH_LOGIN_SUCCESS)
            if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
                return redirect(next_url)
            return redirect('web-home')
    else:
        form = LoginForm()
    return render(request, 'core/pages/auth/login.html', {'form': form, 'next_url': next_url})


@require_POST
@login_required
def logout_page(request):
    logout(request)
    messages.info(request, AUTH_LOGOUT_INFO)
    return redirect('web-home')


def register_page(request):
    if request.user.is_authenticated:
        return redirect('web-home')

    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if not consume_rate_limit(request, 'register'):
            messages.error(request, AUTH_REGISTER_RATE_LIMIT)
            return render(request, 'core/pages/auth/register.html', {'form': form})
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, AUTH_REGISTER_SUCCESS)
            return redirect('web-home')
    else:
        form = RegisterForm()
    return render(request, 'core/pages/auth/register.html', {'form': form})


@login_required
def profile_page(request):
    preference, _ = UserPreference.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        profile_form = UserProfileForm(request.POST, instance=request.user, prefix='profile')
        pref_form = PreferenceForm(request.POST, instance=preference, prefix='pref')
        if profile_form.is_valid() and pref_form.is_valid():
            profile_form.save()
            pref_form.save()
            messages.success(request, PROFILE_SAVE_SUCCESS)
            return redirect('web-profile')
    else:
        profile_form = UserProfileForm(instance=request.user, prefix='profile')
        pref_form = PreferenceForm(instance=preference, prefix='pref')

    return render(
        request,
        'core/pages/auth/profile.html',
        {
            'profile_form': profile_form,
            'pref_form': pref_form,
            'hero_badges': PROFILE_HERO_BADGES,
            'profile_sidebar_panels': build_profile_sidebar_panels(request.user, preference),
        },
    )
