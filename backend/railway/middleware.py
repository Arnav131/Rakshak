"""
railway/middleware.py
Captures the current request.user so signals can attribute audit entries.
"""
import threading

_thread_locals = threading.local()


def get_current_user():
    """Returns the user from the current thread, or None."""
    return getattr(_thread_locals, 'user', None)


class CurrentUserMiddleware:
    """Middleware that stores the current user in thread-local storage."""
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Store user at the start of request
        _thread_locals.user = getattr(request, 'user', None)
        
        # Process the request
        response = self.get_response(request)
        
        # Clean up after request is done
        _thread_locals.user = None
        
        return response

    def process_exception(self, request, exception):
        # Clean up even if there's an error
        _thread_locals.user = None