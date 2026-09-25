"""Read-only wallet and portfolio routes."""

from django.urls import path

from .views import (
    OrderListCreateView,
    PortfolioView,
    TradeListView,
    WalletView,
)

urlpatterns = [
    path("wallet/", WalletView.as_view(), name="wallet"),
    path("portfolio/", PortfolioView.as_view(), name="portfolio"),
    path("orders/", OrderListCreateView.as_view(), name="orders"),
    path("trades/", TradeListView.as_view(), name="trades"),
]
