from .base import *
from corsheaders.defaults import default_headers
import dj_database_url

DEBUG = env("DEBUG")

ALLOWED_HOSTS = env("ALLOWED_HOSTS")
from .base import *


CORS_ALLOW_ALL_ORIGINS = False

CORS_ALLOW_HEADERS = [*default_headers, *env("CORS_ALLOW_HEADERS")]

CORS_ALLOWED_ORIGINS = env("CORS_ALLOWED_ORIGINS")

CSRF_TRUSTED_ORIGINS = env("CSRF_TRUSTED_ORIGINS")


# --------------------------------------------------
# Static files
# --------------------------------------------------

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}


# --------------------------------------------------
# Database
# --------------------------------------------------

DATABASES = {
    "default": dj_database_url.parse(env("MYSQL_URL"))
}
# --------------------------------------------------
# Database
# --------------------------------------------------

BREVO_API_KEY=env("BREVO_API_KEY")
BREVO_SENDER_EMAIL=env("BREVO_SENDER_EMAIL")


# temp code

print("DB_NAME:", env("DB_NAME"))
print("DB_USER:", env("DB_USER"))
print("DB_HOST:", env("DB_HOST"))
print("DB_PORT:", env("DB_PORT"))