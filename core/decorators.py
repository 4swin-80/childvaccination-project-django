from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required

def admin_only(view_func):
    @login_required
    def wrapper(request, *args, **kwargs):
        if request.user.role == 'ADMIN':
            return view_func(request, *args, **kwargs)
        return redirect('login')
    return wrapper
