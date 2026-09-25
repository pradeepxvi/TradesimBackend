from django.core.cache import cache
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .clients.sharehub import InvalidSymbolError, ShareHubClient, ShareHubError
from .serializers import (
    CandleSerializer,
    ChangeSummarySerializer,
    CompanyQuoteSerializer,
    CompanySerializer,
    GainerLoserSerializer,
    IndexSerializer,
    MarketOverviewSerializer,
    MarketStatusSerializer,
)

CACHE_SECONDS = 30


def market_error_response(error):
    if isinstance(error, InvalidSymbolError):
        return Response(
            {"detail": "Invalid market symbol."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return Response(
        {"detail": "Market data is temporarily unavailable."},
        status=status.HTTP_503_SERVICE_UNAVAILABLE,
    )


def get_cached(key, fetch):
    value = cache.get(key)
    if value is None:
        value = fetch()
        cache.set(key, value, CACHE_SECONDS)
    return value


def serialize_or_error(serializer_class, data, many=False):
    serializer = serializer_class(data=data, many=many)
    if not serializer.is_valid():
        return None
    return serializer.data


def company_list_from_overview(overview):
    return overview.get("companies", [])


class MarketStatusView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(tags=["Market"], responses=MarketStatusSerializer)
    def get(self, request):
        try:
            data = get_cached("market:status", ShareHubClient().get_market_status)
            result = {"status": data.get("status", "")}
            if data.get("updated_at") is not None:
                result["time"] = data["updated_at"]
            serialized = serialize_or_error(MarketStatusSerializer, result)
            if serialized is None:
                return market_error_response(ShareHubError())
            return Response(serialized)
        except (ShareHubError, InvalidSymbolError) as error:
            return market_error_response(error)


class MarketOverviewView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(tags=["Market"], responses=MarketOverviewSerializer)
    def get(self, request):
        try:
            data = get_cached("market:overview", ShareHubClient().get_home_page_data)
            overview = {}
            market_status = data.get("market_status")
            if isinstance(market_status, dict):
                overview["market_status"] = {
                    "status": market_status.get("status", ""),
                    "time": market_status.get("updated_at"),
                }
            for key in (
                "market_summary",
                "stock_summary",
                "indices",
                "top_gainers",
                "top_losers",
                "top_turnover",
                "top_traded_shares",
                "top_transactions",
            ):
                if key in data:
                    overview[key] = data[key]
            serialized = serialize_or_error(MarketOverviewSerializer, overview)
            if serialized is None:
                return market_error_response(ShareHubError())
            return Response(serialized)
        except ShareHubError as error:
            return market_error_response(error)


class CompanyListView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(tags=["Market"], responses=CompanySerializer(many=True))
    def get(self, request):
        try:
            data = get_cached("market:overview", ShareHubClient().get_home_page_data)
            serialized = serialize_or_error(
                CompanySerializer,
                company_list_from_overview(data),
                many=True,
            )
            if serialized is None:
                return market_error_response(ShareHubError())
            return Response(serialized)
        except ShareHubError as error:
            return market_error_response(error)


class CompanyDetailView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(tags=["Market"], responses=CompanyQuoteSerializer)
    def get(self, request, symbol):
        try:
            normalized_symbol = ShareHubClient._validate_symbol(symbol)
            data = get_cached("market:overview", ShareHubClient().get_home_page_data)
            company = next(
                (
                    item
                    for item in company_list_from_overview(data)
                    if str(item.get("symbol", "")).strip().upper() == normalized_symbol
                ),
                None,
            )
            if company is None:
                return Response(
                    {"detail": "Company was not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )
            serialized = serialize_or_error(CompanyQuoteSerializer, company)
            if serialized is None:
                return market_error_response(ShareHubError())
            return Response(serialized)
        except (ShareHubError, InvalidSymbolError) as error:
            return market_error_response(error)


class CompanyCandlesView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(tags=["Market"], responses=CandleSerializer(many=True))
    def get(self, request, symbol):
        try:
            candles = ShareHubClient().get_company_candles(symbol)
            serialized = serialize_or_error(CandleSerializer, candles, many=True)
            if serialized is None:
                return market_error_response(ShareHubError())
            return Response(serialized)
        except (ShareHubError, InvalidSymbolError) as error:
            return market_error_response(error)


class IndexCandlesView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(tags=["Market"], responses=CandleSerializer(many=True))
    def get(self, request, symbol):
        try:
            candles = ShareHubClient().get_index_candles(symbol)
            serialized = serialize_or_error(CandleSerializer, candles, many=True)
            if serialized is None:
                return market_error_response(ShareHubError())
            return Response(serialized)
        except (ShareHubError, InvalidSymbolError) as error:
            return market_error_response(error)


class GainersLosersView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=["Market"],
        responses={
            200: {
                "type": "object",
                "properties": {
                    "gainers": {
                        "type": "array",
                        "items": {"$ref": "#/components/schemas/Company"},
                    },
                    "losers": {
                        "type": "array",
                        "items": {"$ref": "#/components/schemas/Company"},
                    },
                },
            }
        },
    )
    def get(self, request):
        try:
            data = ShareHubClient().get_top_gainers_losers()
            gainers = serialize_or_error(
                GainerLoserSerializer, data.get("gainers", []), many=True
            )
            losers = serialize_or_error(
                GainerLoserSerializer, data.get("losers", []), many=True
            )
            if gainers is None or losers is None:
                return market_error_response(ShareHubError())
            return Response({"gainers": gainers, "losers": losers})
        except ShareHubError as error:
            return market_error_response(error)


class ChangeSummaryView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(tags=["Market"], responses=ChangeSummarySerializer(many=True))
    def get(self, request, symbol):
        try:
            data = ShareHubClient().get_change_summary(symbol)
            serialized = serialize_or_error(ChangeSummarySerializer, data, many=True)
            if serialized is None:
                return market_error_response(ShareHubError())
            return Response(serialized)
        except (ShareHubError, InvalidSymbolError) as error:
            return market_error_response(error)
