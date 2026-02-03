from django.urls import path

from user.views.auth import AuthAsyncViewSet


urlpatterns = [
    path("login/", AuthAsyncViewSet.as_view({
        'get': "page",
        'post': 'login',
    }), name='login'),

    path("register/", AuthAsyncViewSet.as_view({
        'get': "register_page",
        'post': 'register',
    }), name='register'),


    path("logout/", AuthAsyncViewSet.as_view({
        'get': "logout",
    }), name='logout'),
]
