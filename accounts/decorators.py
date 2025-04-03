from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied

from accounts import admin
from accounts.models import Book

def admin_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_admin():
            raise PermissionDenied
        return view_func(request, *args, **kwargs)
    return wrapper

def librarian_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or not (request.user.is_librarian() or request.user.is_admin()):
            raise PermissionDenied
        return view_func(request, *args, **kwargs)
    return wrapper

def member_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_member():
            raise PermissionDenied
        return view_func(request, *args, **kwargs)
    return wrapper

