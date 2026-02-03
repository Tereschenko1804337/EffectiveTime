from django.urls import path

from telegram_app.webapp import TelegramWebAppAsyncViewSet


urlpaterns = [
    path("tg/", TelegramWebAppAsyncViewSet.as_view({"get": "page"})),
    path("tg/login/", TelegramWebAppAsyncViewSet.as_view({"post": "login_webapp"})),
    path("tg/bind/", TelegramWebAppAsyncViewSet.as_view({"get": "bind_page", "post": "bind_login"})),
]
