from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from .page.urls import urlpaterns as templates_urls
from .user.auth import urlpatterns as auth_urls
from .user.urls import urlpatterns as user_urls
from .common.urls import urlpatterns as common_urls
from .task.urls import urlpaterns as task_urls
from .telegram.urls import urlpaterns as telegram_urls


urlpatterns = [
    path('', include(auth_urls)),
    path("", include(user_urls)),
    path("", include(templates_urls)),
    path("", include(common_urls)),
    path('task/', include(task_urls)),
    path("", include(telegram_urls)),
    path('social-auth/', include('social_django.urls', namespace='social')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
