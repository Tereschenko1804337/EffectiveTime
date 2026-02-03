import os
import environ
from pathlib import Path


# Путь к директории src
BASE_DIR = Path(__file__).resolve().parent.parent
env = environ.Env(DEBUG=(bool, False))
for env_path in (BASE_DIR / '.env', BASE_DIR.parent / '.env'):
    if os.path.exists(env_path):
        environ.Env.read_env(str(env_path))
        break


# Принцп старта проекта
DEBUG = env.bool('DEBUG', default=False)
SECRET_KEY = env.str('SECRET_KEY', default='dev-insecure') if DEBUG else env.str('SECRET_KEY')

# Адреса с которых можно подключаться к проекту. По умолчанию * - ЛЮБЫЕ
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['*'])
CSRF_TRUSTED_ORIGINS = env.list('CSRF_TRUSTED_ORIGINS', default=[])

# Списки подключёенных приложений (APPS и INSTALLED_APPS)
APPS = [
    'user',
    'task',
    'common',
    'telegram_app',
]

INSTALLED_APPS = [
    'daphne',
    'rest_framework',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'social_django',
    'channels',
] + APPS

# Промежуточное ПО
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'social_django.middleware.SocialAuthExceptionMiddleware',
]

# Путиь к файлу, куда приходят сигналы для проверки пути
ROOT_URLCONF = 'presentation.urls'
AUTH_USER_MODEL = 'user.User'

TELEGRAM_BOT_TOKEN = env.str("TELEGRAM_BOT_TOKEN", default=env.str("BOT_TOKEN", default=""))

# Путь и настройка дерикторий в корторых все HTML
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'social_django.context_processors.backends',
                'social_django.context_processors.login_redirect',
            ],
        },
    },
]

ASGI_APPLICATION = 'effi_time.asgi.application'


# Списко подключённх бд
DB_ENGINE = env.str('DB_ENGINE', default='django.db.backends.sqlite3')
if DB_ENGINE.endswith('sqlite3'):
    DATABASES = {
        'default': {
            'ENGINE': DB_ENGINE,
            'NAME': str(BASE_DIR / 'db.sqlite3'),
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': DB_ENGINE,
            'NAME': env.str('DB_NAME', default='time_shape_manager'),
            'USER': env.str('DB_USER', default='time_shape_manager'),
            'PASSWORD': env.str('DB_PASSWORD', default='time_shape_manager'),
            'HOST': env.str('DB_HOST', default='db'),
            'PORT': env.str('DB_PORT', default='5432'),
        }
    }


SOCIAL_AUTH_VK_OAUTH2_API_VERSION = '5.131'
SOCIAL_AUTH_REDIRECT_IS_HTTPS = True
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

AUTHENTICATION_BACKENDS = (
    'social_core.backends.vk.VKOAuth2',
    'social_core.backends.google.GoogleOAuth2',
    'django.contrib.auth.backends.ModelBackend',
)

SOCIAL_AUTH_VK_OAUTH2_KEY = env.str('VK_KEY', default='')
SOCIAL_AUTH_VK_OAUTH2_SECRET = env.str('VK_SECRET', default='')
SOCIAL_AUTH_VK_OAUTH2_SCOPE = ['email']

SOCIAL_AUTH_GOOGLE_OAUTH2_KEY = env.str('GOOGLE_KEY', default='')
SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET = env.str('GOOGLE_SECRET', default='')

LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/login/'


LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Europe/Moscow'

USE_I18N = True

USE_TZ = True

# Путь к статик папке
STATIC_URL = '/static/'
STATIC_ROOT = str(BASE_DIR / 'staticfiles')
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),
]

# Путь к папке мдеиа
MEDIA_URL = '/media/'
MEDIA_ROOT = str(BASE_DIR / 'media')


DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [(env.str('REDIS_HOST', default='127.0.0.1'), env.int('REDIS_PORT', default=6379))],
        },
    },
}
