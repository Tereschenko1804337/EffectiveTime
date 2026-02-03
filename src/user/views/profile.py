from adrf.requests import AsyncRequest
from rest_framework import status
from rest_framework.response import Response
from adrf.viewsets import ViewSet
from rest_framework.parsers import MultiPartParser, FormParser
from django.core import signing

from domain.schemas.user.main import ChangePasswordDTO
from infrastructure.comon.authetication import AsyncAuthentication
from infrastructure.comon.login_decorator import login_required


class UserProfileAsyncViewSet(ViewSet):
    authentication_classes = [AsyncAuthentication]
    parser_classes = [MultiPartParser, FormParser]

    @login_required
    async def retrieve(self, request: AsyncRequest):
        user = request.user
        if not user.is_authenticated:
            return Response(status=status.HTTP_401_UNAUTHORIZED)
        
        avatar_url = user.avatar.url if user.avatar else user.photo_url

        payload = {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "avatar": avatar_url,
            "theme": getattr(user, "theme", "dark"),
            "wake_up_time": user.wake_up_time.strftime("%H:%M") if user.wake_up_time else None,
            "bed_time": user.bed_time.strftime("%H:%M") if user.bed_time else None,
        }
        return Response(data=payload, status=status.HTTP_200_OK)

    @login_required
    async def wallpaper_token(self, request: AsyncRequest):
        user = request.user
        if not user.is_authenticated:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        token = signing.dumps({"uid": user.id}, salt="effi_time_wallpaper")
        return Response(
            data={
                "token": token,
                "max_age_seconds": 60 * 60 * 24 * 30,
            },
            status=status.HTTP_200_OK,
        )

    @login_required
    async def change_password(self, request: AsyncRequest):
        user = request.user
        try:
            dto = ChangePasswordDTO(**(request.data or {}))
        except Exception as exc:
            return Response(data={"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        if not user.check_password(dto.old_password):
            return Response(data={"detail": "Неверный текущий пароль"}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(dto.new_password)
        await user.asave()
        # Note: Session auth might be lost after password change depending on Django version/setup.
        # But we are using session auth, so usually `update_session_auth_hash` is needed.
        # Since this is async and custom, let's see. For now, just save.
        
        return Response(data={"detail": "Пароль успешно изменен"}, status=status.HTTP_200_OK)

    @login_required
    async def upload_avatar(self, request: AsyncRequest):
        user = request.user
        if 'avatar' not in request.FILES:
            return Response(data={"detail": "Файл не найден"}, status=status.HTTP_400_BAD_REQUEST)
        
        file = request.FILES['avatar']
        user.avatar = file
        await user.asave()
        
        return Response(data={"avatar": user.avatar.url}, status=status.HTTP_200_OK)
