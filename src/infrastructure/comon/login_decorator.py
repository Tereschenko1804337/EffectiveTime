from django.shortcuts import redirect
from django.urls import reverse_lazy


def login_required(view_func):
    async def wrapper(cls, *args, **kwargs):
        auth = cls.request.headers.get("Authetisation")
        not_auth = False

        if not cls.request.user.is_authenticated:
            not_auth = True

        if not_auth:
            return redirect(reverse_lazy('login'))

        return await view_func(cls, *args, **kwargs)

    return wrapper