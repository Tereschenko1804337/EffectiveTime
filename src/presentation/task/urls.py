from django.urls import path

from task.views.main import TaskAsyncViewSet
from task.views.analytics import AnalyticsAsyncViewSet
from task.views.wallpaper import TaskWallpaperAsyncViewSet

urlpaterns = [
    path('analytics/', AnalyticsAsyncViewSet.as_view({
        'get': 'get_page',
    })),
    path('analytics/data/', AnalyticsAsyncViewSet.as_view({
        'get': 'get_stats',
    })),
    path('analytics/ai-report/', AnalyticsAsyncViewSet.as_view({
        'post': 'get_ai_report',
    })),
    path('creating/', TaskAsyncViewSet.as_view({
        'get': 'creation_page_info',
        'post': 'create',
    })),
    path('tags/', TaskAsyncViewSet.as_view({
        'post': 'create_tag',
    })),
    path('calendar/', TaskAsyncViewSet.as_view({
        'get': 'list_calendar',
    })),
    path('today/', TaskAsyncViewSet.as_view({
        'get': 'list_today',
    })),
    path('wallpaper/today.png', TaskWallpaperAsyncViewSet.as_view({
        'get': 'today',
    })),
    path('<int:task_id>/updating/', TaskAsyncViewSet.as_view({
        'patch': 'update',
    })),
    path('<int:task_id>/timing/', TaskAsyncViewSet.as_view({
        'patch': 'update_timing',
    })),
    path('<int:task_id>/subtasks/<int:subtask_id>/completed/', TaskAsyncViewSet.as_view({
        'patch': 'update_subtask_completed',
    })),
    path('canban/', TaskAsyncViewSet.as_view({
        'get': 'get_canaban_table',
    })),
    path('<int:task_id>/status/', TaskAsyncViewSet.as_view({
        'patch': 'update_status',
    })),
path('<int:task_id>/view/', TaskAsyncViewSet.as_view({
        'get': 'retrive',
    })),
    path('<int:task_id>/comments/', TaskAsyncViewSet.as_view({
        'get': 'list_comments',
        'post': 'create_comment',
    })),
    path('<int:task_id>/history/', TaskAsyncViewSet.as_view({
        'get': 'list_history',
    })),
]
