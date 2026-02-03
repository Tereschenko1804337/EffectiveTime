from adrf.requests import AsyncRequest
from asgiref.sync import sync_to_async
from django.core import signing
from rest_framework.authentication import BaseAuthentication

from user.models import User


class AsyncAuthentication(BaseAuthentication):
    async def authenticate(self, request: AsyncRequest):
        user_id = await sync_to_async(lambda: request.session.get('_auth_user_id'))()

        try:
            user = await User.objects.aget(pk=user_id)

            return user, None

        except User.DoesNotExist:
            pass

        except Exception:
            pass

        tg_token = request.COOKIES.get("tg_token") or request.headers.get("X-Tg-Token") or ""
        if not tg_token:
            return None

        try:
            payload = signing.loads(tg_token, salt="effi_time_tg_access", max_age=60 * 60 * 24 * 365)
            tg_id = payload.get("tg_id")
            if tg_id is not None:
                user = await User.objects.aget(tg_id=int(tg_id))
            else:
                uid = int(payload.get("uid"))
                user = await User.objects.aget(pk=uid)
            return user, None
        except Exception:
            return None
