# backend/core/views.py
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.views.decorators.http import require_http_methods


@require_http_methods(["GET", "POST"])
def custom_logout_view(request):
    """
    Log out the user and redirect to the login page.
    Handles both GET and POST requests smoothly across Django versions.
    """
    logout(request)
    return redirect('login')
