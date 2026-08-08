"""Authentication-related forms."""

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

USER_MODEL = get_user_model()


class RegisterForm(UserCreationForm):
    """Registration form with required email."""

    email = forms.EmailField(required=True, label='Email', widget=forms.EmailInput(attrs={'autocomplete': 'email'}))
    first_name = forms.CharField(
        required=True,
        max_length=150,
        label='First name',
        widget=forms.TextInput(attrs={'autocomplete': 'given-name'}),
    )
    last_name = forms.CharField(
        required=True,
        max_length=150,
        label='Last name',
        widget=forms.TextInput(attrs={'autocomplete': 'family-name'}),
    )

    class Meta:
        model = USER_MODEL
        fields = ('username', 'email', 'first_name', 'last_name', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].label = 'Username'
        self.fields['password1'].label = 'Password'
        self.fields['password2'].label = 'Confirm password'
        # BaseUserCreationForm adds autofocus to username; moving focus on page
        # load disorients screen-reader and keyboard users, so drop it.
        self.fields['username'].widget.attrs.pop('autofocus', None)
        self.fields['username'].widget.attrs.setdefault('autocomplete', 'username')
        self.fields['password1'].widget.attrs.setdefault('autocomplete', 'new-password')
        self.fields['password2'].widget.attrs.setdefault('autocomplete', 'new-password')
        # Password rules surface as validation errors on submit instead of a
        # preemptive bullet list under an untouched field.
        self.fields['password1'].help_text = ''
        self.fields['password2'].help_text = ''


class LoginForm(AuthenticationForm):
    """Sign-in form fields used by the login page."""

    username = forms.CharField(label='Username', widget=forms.TextInput(attrs={'autocomplete': 'username'}))
    password = forms.CharField(label='Password', widget=forms.PasswordInput(attrs={'autocomplete': 'current-password'}))
