from adrf.requests import AsyncRequest
from adrf.viewsets import ViewSet
from asgiref.sync import sync_to_async
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from rest_framework import status
from rest_framework.response import Response

from user.models import User


class AuthAsyncViewSet(ViewSet):

    async def page(
            self,
            request: AsyncRequest,
    ):
        return render(
            request=request,
            template_name='user/login.html',
            context={
                'title': 'Авторизация',
            },
        )

    async def register_page(
            self,
            request: AsyncRequest,
    ):
        return render(
            request=request,
            template_name='user/register.html',
            context={
                'title': 'Регистрация',
            },
        )

    async def login(
        self,
        request: AsyncRequest,
    ):
        data = request.data

        try:
            user = await User.objects.aget(username=data['username'])
        except Exception:
            return Response(data={
                'detail': 'Нет такого пользователя!'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = await sync_to_async(authenticate)(
                request=request,
                username=user.username,
                password=data['password'],
            )
            if user is None:
                raise Exception
        except Exception:
            return Response(data={
                'detail': 'Неверный пароль!'
            }, status=status.HTTP_400_BAD_REQUEST)

        await sync_to_async(login)(request, user)

        return Response(data={}, status=status.HTTP_204_NO_CONTENT)

    async def register(
        self,
        request: AsyncRequest,
    ):
        data = request.data
        username = (data.get('username') or '').strip()
        password = data.get('password') or ''
        password2 = data.get('password2') or ''

        if not username or not password:
            return Response(data={'detail': 'Заполните username и password.'}, status=status.HTTP_400_BAD_REQUEST)

        if password != password2:
            return Response(data={'detail': 'Пароли не совпадают.'}, status=status.HTTP_400_BAD_REQUEST)

        username_taken = await sync_to_async(User.objects.filter(username=username).exists)()
        if username_taken:
            return Response(data={'detail': 'Username уже занят.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            await sync_to_async(validate_password)(password)
        except ValidationError as e:
            detail = '\n'.join(e.messages) if getattr(e, 'messages', None) else 'Некорректный пароль.'
            return Response(data={'detail': detail}, status=status.HTTP_400_BAD_REQUEST)

        try:
            created_user = await sync_to_async(User.objects.create_user)(
                username=username,
                password=password,
            )
        except IntegrityError:
            return Response(data={'detail': 'Username уже занят.'}, status=status.HTTP_400_BAD_REQUEST)

        user = await sync_to_async(authenticate)(
            request=request,
            username=created_user.username,
            password=password,
        )
        if user is None:
            return Response(data={'detail': 'Не удалось войти после регистрации.'}, status=status.HTTP_400_BAD_REQUEST)

        await sync_to_async(login)(request, user)
        return Response(data={}, status=status.HTTP_204_NO_CONTENT)

    async def logout(
        self,
        request: AsyncRequest,
    ):
        await sync_to_async(logout)(request)

        return redirect(reverse_lazy('login'))
