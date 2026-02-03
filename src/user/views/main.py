from __future__ import annotations

from datetime import datetime

from adrf.requests import AsyncRequest
from adrf.viewsets import ViewSet
from rest_framework import status
from rest_framework.response import Response

from domain.schemas.user.main import SleepSettingsRetrieveDTO, SleepSettingsUpdateDTO, ThemeRetrieveDTO, ThemeUpdateDTO
from infrastructure.comon.authetication import AsyncAuthentication
from infrastructure.comon.login_decorator import login_required


class UserSleepSettingsAsyncViewSet(ViewSet):
    authentication_classes = [AsyncAuthentication]

    @login_required
    async def retrieve(self, request: AsyncRequest):
        user = request.user
        if not user.is_authenticated:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        wake = getattr(user, "wake_up_time", None)
        bed = getattr(user, "bed_time", None)

        payload = SleepSettingsRetrieveDTO(
            wake_up_time=wake.strftime("%H:%M") if wake else "08:00",
            bed_time=bed.strftime("%H:%M") if bed else "23:00",
        ).model_dump()

        return Response(data=payload, status=status.HTTP_200_OK)

    @login_required
    async def update(self, request: AsyncRequest):
        user = request.user
        if not user.is_authenticated:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        try:
            dto = SleepSettingsUpdateDTO(**(request.data or {}))
        except Exception as exc:
            return Response(data={"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        user.wake_up_time = datetime.strptime(dto.wake_up_time, "%H:%M").time()
        user.bed_time = datetime.strptime(dto.bed_time, "%H:%M").time()
        await user.asave(update_fields=["wake_up_time", "bed_time"])

        payload = SleepSettingsRetrieveDTO(
            wake_up_time=dto.wake_up_time,
            bed_time=dto.bed_time,
        ).model_dump()

        return Response(data=payload, status=status.HTTP_200_OK)


class UserThemeAsyncViewSet(ViewSet):
    authentication_classes = [AsyncAuthentication]

    @login_required
    async def retrieve(self, request: AsyncRequest):
        user = request.user
        if not user.is_authenticated:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        theme = getattr(user, "theme", "dark")
        payload = ThemeRetrieveDTO(theme=theme).model_dump()
        return Response(data=payload, status=status.HTTP_200_OK)

    @login_required
    async def update(self, request: AsyncRequest):
        user = request.user
        if not user.is_authenticated:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        try:
            dto = ThemeUpdateDTO(**(request.data or {}))
        except Exception as exc:
            return Response(data={"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        user.theme = dto.theme
        await user.asave(update_fields=["theme"])

        payload = ThemeRetrieveDTO(theme=dto.theme).model_dump()
        return Response(data=payload, status=status.HTTP_200_OK)
