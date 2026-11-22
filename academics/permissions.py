from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect

from .models import PortalAccount


def is_manager(user):
    return user.is_authenticated and user.is_active and user.is_staff and user.has_perm('academics.manage_academics')


def require_manager(user):
    if not is_manager(user):
        raise PermissionDenied


def portal_required(view):
    @wraps(view)
    @login_required(login_url='academics:login')
    def guarded(request, *args, **kwargs):
        account = PortalAccount.objects.filter(user=request.user).first()
        if not request.user.is_active or (not account and not is_manager(request.user)):
            raise PermissionDenied
        if account and account.must_change_password:
            return redirect('academics:password')
        request.portal_account = account
        return view(request, *args, **kwargs)
    return guarded


def manager_required(view):
    @wraps(view)
    @portal_required
    def guarded(request, *args, **kwargs):
        require_manager(request.user)
        return view(request, *args, **kwargs)
    return guarded
