from django.conf import settings
from django.contrib import admin
from django.urls import path, re_path, include
from django.views.static import serve
from first_app.urls import urlpatterns as first_app_urlpatterns


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include(first_app_urlpatterns)),

    re_path(r'^static/(?P<path>,*)$', serve, {'document_root': settings.STATIC_ROOT})
]

if settings.DEBUG:
    urlpatterns.append(
        re_path(
            r'^media/(?P<path>,*)$',
            serve,
            {'document_root': settings.MEDIA_ROOT}
        )
    )