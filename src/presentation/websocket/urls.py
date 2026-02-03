from django.urls import path
from .consumers import TaskConsumer

routes = [
    path('ws/tasks/', TaskConsumer.as_asgi()),
]
