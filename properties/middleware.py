from django.shortcuts import get_object_or_404
from accounts.models import Account


class AccountMiddleware:
    """Middleware to set current account in request"""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            try:
                # For new User model
                if hasattr(request.user, 'account') and request.user.account:
                    request.account = request.user.account
                else:
                    request.account = None
            except (Account.DoesNotExist, AttributeError):
                request.account = None
        else:
            request.account = None
        
        response = self.get_response(request)
        return response

