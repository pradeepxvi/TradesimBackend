from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError
from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema
from rest_framework import permissions, status, viewsets
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response

from apps.market.clients.sharehub import (
    InvalidSymbolError,
    ShareHubClient,
    ShareHubError,
)

from .models import WatchlistItem
from .serializers import WatchlistItemSerializer


class WatchlistViewSet(viewsets.ModelViewSet):
    serializer_class = WatchlistItemSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post", "delete", "head", "options"]
    lookup_field = "symbol"
    symbol_parameter = OpenApiParameter(
        name="symbol",
        type=OpenApiTypes.STR,
        location=OpenApiParameter.PATH,
        description="Uppercase or lowercase company symbol.",
    )

    def get_queryset(self):
        return WatchlistItem.objects.filter(user=self.request.user)

    def _get_market_data(self):
        companies = ShareHubClient().get_home_page_data().get("companies", [])
        return {
            company["symbol"]: company for company in companies if company.get("symbol")
        }

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if self.action in {"list", "retrieve"}:
            context["market_data"] = self._get_market_data()
        return context

    def get_object(self):
        try:
            symbol = ShareHubClient._validate_symbol(self.kwargs[self.lookup_field])
        except InvalidSymbolError as error:
            raise ValidationError({"symbol": "Invalid market symbol."}) from error
        try:
            return self.get_queryset().get(symbol=symbol)
        except ObjectDoesNotExist as error:
            raise NotFound("Watchlist symbol was not found.") from error

    @extend_schema(tags=["Watchlist"])
    def list(self, request, *args, **kwargs):
        try:
            return super().list(request, *args, **kwargs)
        except ShareHubError:
            return self._market_unavailable()

    @extend_schema(tags=["Watchlist"], parameters=[symbol_parameter])
    def retrieve(self, request, *args, **kwargs):
        try:
            return super().retrieve(request, *args, **kwargs)
        except ShareHubError:
            return self._market_unavailable()

    @extend_schema(tags=["Watchlist"])
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            market_data = self._get_market_data()
        except ShareHubError:
            return self._market_unavailable()
        if serializer.validated_data["symbol"] not in market_data:
            raise ValidationError({"symbol": "Company symbol was not found."})
        try:
            self.perform_create(serializer)
        except IntegrityError as error:
            raise ValidationError(
                {"symbol": "Symbol is already in your watchlist."}
            ) from error
        headers = self.get_success_headers(serializer.data)
        return Response(
            serializer.data, status=status.HTTP_201_CREATED, headers=headers
        )

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @extend_schema(tags=["Watchlist"], parameters=[symbol_parameter])
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    @staticmethod
    def _market_unavailable():
        return Response(
            {"detail": "Market data is temporarily unavailable."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


from django.shortcuts import render

# Create your views here.
