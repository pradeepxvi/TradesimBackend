"""Public read-only market-data routes."""

from django.urls import path

from .views import (
    ChangeSummaryView,
    CompanyCandlesView,
    CompanyDetailView,
    CompanyListView,
    GainersLosersView,
    IndexCandlesView,
    MarketOverviewView,
    MarketStatusView,
)

urlpatterns = [
    path("status/", MarketStatusView.as_view(), name="market-status"),
    path("overview/", MarketOverviewView.as_view(), name="market-overview"),
    path("companies/", CompanyListView.as_view(), name="company-list"),
    path(
        "companies/<str:symbol>/",
        CompanyDetailView.as_view(),
        name="company-detail",
    ),
    path(
        "companies/<str:symbol>/candles/",
        CompanyCandlesView.as_view(),
        name="company-candles",
    ),
    path(
        "indices/<str:symbol>/candles/",
        IndexCandlesView.as_view(),
        name="index-candles",
    ),
    path("gainers-losers/", GainersLosersView.as_view(), name="gainers-losers"),
    path(
        "change-summary/<str:symbol>/",
        ChangeSummaryView.as_view(),
        name="change-summary",
    ),
]
