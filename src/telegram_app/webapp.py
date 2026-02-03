import hmac
import hashlib
from urllib.parse import parse_qsl

from adrf.requests import AsyncRequest
from adrf.viewsets import ViewSet
from asgiref.sync import sync_to_async
from django.conf import settings
from django.core import signing
from django.contrib.auth import login, authenticate
from django.shortcuts import render, redirect
from rest_framework import status
from rest_framework.response import Response

from user.models import User


def _verify_init_data(init_data: str, bot_token: str) -> dict | None:
    try:
        pairs = parse_qsl(init_data, keep_blank_values=True)
    except Exception:
        return None

    data = dict(pairs)
    received_hash = data.pop("hash", None)
    if not received_hash:
        return None

    check_string = "\n".join([f"{k}={data[k]}" for k in sorted(data.keys())])
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    computed_hash = hmac.new(secret_key, check_string.encode("utf-8"), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        return None

    return data


class TelegramWebAppAsyncViewSet(ViewSet):
    async def page(self, request: AsyncRequest):
        if request.user and getattr(request.user, "is_authenticated", False):
            return redirect("/today/")

        pending_tg_id = request.session.get("tg_pending_id")
        if pending_tg_id:
            return redirect("/tg/bind/")

        token = request.COOKIES.get("tg_token") or ""
        if token:
            try:
                payload = signing.loads(token, salt="effi_time_tg_access", max_age=60 * 60 * 24 * 365)
                tg_id = payload.get("tg_id")
                if tg_id is not None:
                    user = await User.objects.aget(tg_id=int(tg_id))
                else:
                    uid = int(payload.get("uid"))
                    user = await User.objects.aget(pk=uid)
                await sync_to_async(login)(request, user, backend="django.contrib.auth.backends.ModelBackend")
                request.session["tg_webapp"] = True
                return redirect("/today/")
            except Exception:
                pass

        return render(
            request=request,
            template_name="telegram/webapp.html",
            context={
                "title": "EffiTime",
            },
        )

    async def login_webapp(self, request: AsyncRequest):
        bot_token = getattr(settings, "TELEGRAM_BOT_TOKEN", "") or ""
        if not bot_token:
            return Response(data={"detail": "TELEGRAM_BOT_TOKEN is not configured"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        init_data = (request.data or {}).get("initData") or ""
        init_data = str(init_data)

        verified = _verify_init_data(init_data, bot_token)
        if not verified:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        user_raw = verified.get("user") or ""
        try:
            import json

            user_data = json.loads(user_raw) if isinstance(user_raw, str) else user_raw
        except Exception:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        tg_id = user_data.get("id")
        if not tg_id:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        try:
            user = await User.objects.aget(tg_id=int(tg_id))
        except Exception:
            user = None

        if not user:
            request.session["tg_pending_id"] = int(tg_id)
            return Response(data={"need_bind": True}, status=status.HTTP_409_CONFLICT)

        await sync_to_async(login)(request, user, backend="django.contrib.auth.backends.ModelBackend")
        request.session["tg_webapp"] = True

        tg_token = signing.dumps({"uid": user.id, "tg_id": tg_id}, salt="effi_time_tg_access")
        resp = Response(data={"ok": True}, status=status.HTTP_200_OK)
        resp.set_cookie(
            "tg_token",
            tg_token,
            max_age=60 * 60 * 24 * 365,
            httponly=True,
            samesite="Lax",
            secure=request.is_secure(),
        )
        return resp

    async def bind_page(self, request: AsyncRequest):
        pending_tg_id = request.session.get("tg_pending_id")
        if not pending_tg_id:
            return redirect("/tg/")

        if request.user and getattr(request.user, "is_authenticated", False):
            return redirect("/today/")

        return render(
            request=request,
            template_name="telegram/bind.html",
            context={
                "title": "Привязка Telegram",
            },
        )

    async def bind_login(self, request: AsyncRequest):
        pending_tg_id = request.session.get("tg_pending_id")
        if not pending_tg_id:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        data = request.data or {}
        username = (data.get("username") or "").strip()
        password = data.get("password") or ""
        if not username or not password:
            return Response(data={"detail": "Заполните логин и пароль."}, status=status.HTTP_400_BAD_REQUEST)

        user = await sync_to_async(authenticate)(
            request=request,
            username=username,
            password=password,
        )
        if user is None:
            return Response(data={"detail": "Неверный логин или пароль."}, status=status.HTTP_400_BAD_REQUEST)

        existing_user = None
        try:
            existing_user = await User.objects.aget(tg_id=int(pending_tg_id))
        except Exception:
            existing_user = None

        if existing_user and existing_user.id != user.id:
            return Response(data={"detail": "Этот Telegram уже привязан к другому аккаунту."}, status=status.HTTP_409_CONFLICT)

        if getattr(user, "tg_id", None) and int(user.tg_id) != int(pending_tg_id):
            return Response(data={"detail": "Этот аккаунт уже привязан к другому Telegram."}, status=status.HTTP_409_CONFLICT)

        if not getattr(user, "tg_id", None):
            user.tg_id = int(pending_tg_id)
            await user.asave(update_fields=["tg_id"])

        await sync_to_async(login)(request, user, backend="django.contrib.auth.backends.ModelBackend")
        request.session["tg_webapp"] = True
        try:
            del request.session["tg_pending_id"]
        except Exception:
            pass

        tg_token = signing.dumps({"uid": user.id, "tg_id": int(user.tg_id)}, salt="effi_time_tg_access")
        resp = Response(data={"ok": True}, status=status.HTTP_200_OK)
        resp.set_cookie(
            "tg_token",
            tg_token,
            max_age=60 * 60 * 24 * 365,
            httponly=True,
            samesite="Lax",
            secure=request.is_secure(),
        )
        return resp
