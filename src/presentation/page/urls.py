from django.urls import path
from common.views.page import TemplatesAsyncViewsSet
from task.views.page import TemplatesTaskAsyncViewsSet


urlpaterns = [
    path('', TemplatesAsyncViewsSet.as_view({
        "get": "get_category_page"
    })),

    path('today/', TemplatesAsyncViewsSet.as_view({
        "get": "get_today_page"
    })),

    path('calendar/', TemplatesAsyncViewsSet.as_view({
        "get": "get_calendar_page"
    })),

    path('canban/', TemplatesAsyncViewsSet.as_view({
        "get": "get_canban_page"
    })),
    path('task/create/', TemplatesTaskAsyncViewsSet.as_view({
        "get": "get_create_page",
    })),
    path('task/view/', TemplatesTaskAsyncViewsSet.as_view({
        "get": "get_view_page",
    })),
    path("profile/", TemplatesAsyncViewsSet.as_view({"get": "get_profile_page"})),
]
