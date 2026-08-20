"""Root URL routing for Sigma Taste."""

from django.urls import include, path

urlpatterns = [
    path('', include('core.urls')),
]
