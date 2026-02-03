from django.urls import path

from common.views.main import CategoryAsyncViewSet

urlpatterns = [
    path('category/list/', CategoryAsyncViewSet.as_view({
        'get': 'get',
    })),
    path('category/create/', CategoryAsyncViewSet.as_view({
        'post': 'create',
    })),
    path('category/update/<int:pk>/', CategoryAsyncViewSet.as_view({
        'patch': 'update',
    })),
]