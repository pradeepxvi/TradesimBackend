"""Root URL configuration for the Tradesim backend."""

from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/auth/", include("apps.users.urls")),
    path("api/v1/profile/", include("apps.users.profile_urls")),
    path("api/v1/market/", include("apps.market.urls")),
    path("api/v1/trading/", include("apps.trading.urls")),
    path("api/v1/watchlist/", include("apps.watchlist.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
