from django.urls import path

from user.views.main import UserSleepSettingsAsyncViewSet, UserThemeAsyncViewSet
from user.views.profile import UserProfileAsyncViewSet

urlpatterns = [
    path(
        "user/sleep/",
        UserSleepSettingsAsyncViewSet.as_view(
            {
                "get": "retrieve",
                "put": "update",
                "patch": "update",
            }
        ),
    ),
    path(
        "user/theme/",
        UserThemeAsyncViewSet.as_view(
            {
                "get": "retrieve",
                "put": "update",
                "patch": "update",
            }
        ),
    ),
    path(
        "user/profile/",
        UserProfileAsyncViewSet.as_view(
            {
                "get": "retrieve",
            }
        ),
    ),
    path(
        "user/wallpaper/token/",
        UserProfileAsyncViewSet.as_view(
            {
                "get": "wallpaper_token",
            }
        ),
    ),
    path(
        "user/profile/password/",
        UserProfileAsyncViewSet.as_view(
            {
                "post": "change_password",
            }
        ),
    ),
    path(
        "user/profile/avatar/",
        UserProfileAsyncViewSet.as_view(
            {
                "post": "upload_avatar",
            }
        ),
    ),
]
