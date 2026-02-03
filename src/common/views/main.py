from adrf.requests import AsyncRequest
from adrf.viewsets import ViewSet
from rest_framework import status
from rest_framework.response import Response

from common.models import Category
from domain.schemas.task.common import CategoryRetriveDTO, CategoryCreateDTO
from infrastructure.comon.authetication import AsyncAuthentication
from infrastructure.comon.login_decorator import login_required


class CategoryAsyncViewSet(ViewSet):
    authentication_classes = [AsyncAuthentication]

    @login_required
    async def get(
        self,
        request: AsyncRequest,
    ):
        user = request.user
        if not user.is_authenticated:
            return Response(status=status.HTTP_401_UNAUTHORIZED)


        categories = Category.objects.filter(user_id=user.id)
        category_list = [
            CategoryRetriveDTO.model_validate(category).model_dump()
            async for category in categories
        ]

        return Response(data=category_list)

    @login_required
    async def create(
        self,
        request: AsyncRequest,
    ):
        user = request.user
        if not user.is_authenticated:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        try:
            category_dto = CategoryCreateDTO(**request.data)
            category = await Category.objects.acreate(
                name=category_dto.name,
                user=user
            )
            return Response(
                data=CategoryRetriveDTO.model_validate(category).model_dump(),
                status=status.HTTP_201_CREATED
            )
        except Exception as e:
            return Response(status=status.HTTP_400_BAD_REQUEST)

    @login_required
    async def update(
        self,
        request: AsyncRequest,
        pk: int,
    ):
        user = request.user
        if not user.is_authenticated:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        try:
            category_dto = CategoryCreateDTO(**request.data)
            category = await Category.objects.aget(id=pk, user=user)
            category.name = category_dto.name
            await category.asave()
            
            return Response(
                data=CategoryRetriveDTO.model_validate(category).model_dump(),
                status=status.HTTP_200_OK
            )
        except Category.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response(status=status.HTTP_400_BAD_REQUEST)

