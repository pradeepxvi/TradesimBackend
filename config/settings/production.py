from .base import *
from corsheaders.defaults import default_headers

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

print("=== PRODUCTION SETTINGS ===")
print("ROOT_URLCONF:", ROOT_URLCONF)
print("SETTINGS LOADED: production.py")