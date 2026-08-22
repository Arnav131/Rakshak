"""
core/utils.py
Shared helpers for the Rakshak project.

This module provides reusable decorators and utilities used across
multiple apps in the project. All decorators here are designed for
API endpoints, returning JSON error responses instead of HTML redirects.

Decorators:
    api_login_required         - Returns 401 JSON for unauthenticated API calls
    api_staff_required         - Returns 403 JSON for non-staff users
    api_permission_required    - Checks specific Django permissions
    
Usage Example:
    from core.utils import api_login_required
    
    @api_login_required
    def my_api_view(request):
        return JsonResponse({'data': 'protected'})
"""

from functools import wraps
from django.http import JsonResponse


def api_login_required(view_func):
    """
    Decorator for API views that require authentication.
    
    Unlike Django's @login_required which redirects to login page (HTML),
    this decorator returns a 401 JSON response. This is essential for:
    - AJAX/fetch API calls
    - Leaflet map tile requests
    - Mobile app API calls
    - Any non-browser HTTP client
    
    Args:
        view_func: The view function to decorate
        
    Returns:
        wrapper: Decorated function that checks authentication
        
    Response on failure:
        {"error": "Authentication required", "detail": "..."}
        Status: 401 Unauthorized
        
    Example:
        @api_login_required
        def get_sensor_data(request):
            return JsonResponse({'temperature': 25.5})
    """
    @wraps(view_func)  # Preserves original function's metadata (name, docstring, etc.)
    def wrapper(request, *args, **kwargs):
        # Check if user is authenticated via session or token
        if not request.user.is_authenticated:
            return JsonResponse({
                'error': 'Authentication required',
                'detail': 'Please provide valid credentials to access this endpoint.'
            }, status=401)
        
        # User is authenticated, proceed with the original view
        return view_func(request, *args, **kwargs)
    
    return wrapper


def api_staff_required(view_func):
    """
    Decorator for API views that require staff (admin) privileges.
    
    First checks authentication (returns 401 if not logged in),
    then checks staff status (returns 403 if not staff).
    
    Args:
        view_func: The view function to decorate
        
    Returns:
        wrapper: Decorated function that checks auth and staff status
        
    Response on auth failure:
        {"error": "Authentication required", ...}
        Status: 401
        
    Response on permission failure:
        {"error": "Permission denied", ...}
        Status: 403
        
    Example:
        @api_staff_required
        def admin_dashboard_api(request):
            return JsonResponse({'stats': {...}})
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # First check: Is the user authenticated?
        if not request.user.is_authenticated:
            return JsonResponse({
                'error': 'Authentication required',
                'detail': 'Please log in to access this endpoint.'
            }, status=401)
        
        # Second check: Does the user have staff privileges?
        if not request.user.is_staff:
            return JsonResponse({
                'error': 'Permission denied',
                'detail': 'Staff privileges are required for this endpoint.'
            }, status=403)
        
        # Both checks passed, execute the view
        return view_func(request, *args, **kwargs)
    
    return wrapper


def api_permission_required(permission_name):
    """
    Decorator factory that checks if the user has a specific Django permission.
    
    This is a decorator factory (returns a decorator) because it accepts
    the permission name as an argument.
    
    Args:
        permission_name (str): Django permission string, e.g.:
            - 'railway.can_view_sensor_data'
            - 'auth.change_user'
            - 'sensors.add_sensorreading'
            
    Returns:
        decorator: Actual decorator function
        
    Response on auth failure:
        {"error": "Authentication required", ...}
        Status: 401
        
    Response on permission failure:
        {"error": "Permission denied", ...}
        Status: 403
        
    Example:
        @api_permission_required('railway.can_manage_alerts')
        def resolve_alert_api(request, alert_id):
            return JsonResponse({'status': 'resolved'})
    """
    def decorator(view_func):
        """
        Inner decorator function that wraps the view.
        """
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Step 1: Ensure user is logged in
            if not request.user.is_authenticated:
                return JsonResponse({
                    'error': 'Authentication required',
                    'detail': 'Please log in to access this endpoint.'
                }, status=401)
            
            # Step 2: Check specific permission using Django's permission system
            # has_perm() checks both user permissions and group permissions
            if not request.user.has_perm(permission_name):
                return JsonResponse({
                    'error': 'Permission denied',
                    'detail': f'You need the "{permission_name}" permission to perform this action.'
                }, status=403)
            
            # All checks passed, execute the original view
            return view_func(request, *args, **kwargs)
        
        return wrapper
    
    return decorator