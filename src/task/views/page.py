from adrf.requests import AsyncRequest
from adrf.viewsets import ViewSet
from django.shortcuts import render

from infrastructure.comon.authetication import AsyncAuthentication
from infrastructure.comon.login_decorator import login_required


class TemplatesTaskAsyncViewsSet(ViewSet):
    authentication_classes = [AsyncAuthentication]

    @login_required
    async def get_create_page(
        self,
        request: AsyncRequest,
    ):
        context = {

        }

        return render(
            request,
            template_name='task/create.html',
            context=context,
        )

    @login_required
    async def get_view_page(
        self,
        request: AsyncRequest,
    ):
        context = {

        }

        return render(
            request,
            template_name='task/view.html',
            context=context,
        )