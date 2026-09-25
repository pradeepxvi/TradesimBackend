from decimal import Decimal

from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.market.clients.sharehub import ShareHubClient, ShareHubError

from .models import Holding, Wallet
from .models import Order, Trade
from .serializers import (
    OrderCreateSerializer,
    OrderSerializer,
    PortfolioHoldingSerializer,
    TradeSerializer,
    WalletSerializer,
)
from .services import (
    MarketClosedError,
    MarketUnavailableError,
    TradingError,
    TradingService,
)


class WalletView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(tags=["Trading"], responses=WalletSerializer)
    def get(self, request):
        wallet, _ = Wallet.objects.get_or_create(
            user=request.user,
            defaults={"virtual_balance": settings.INITIAL_VIRTUAL_BALANCE},
        )
        return Response(WalletSerializer(wallet).data)


class PortfolioView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(tags=["Trading"], responses=PortfolioHoldingSerializer(many=True))
    def get(self, request):
        holdings = list(Holding.objects.filter(user=request.user))
        try:
            companies = ShareHubClient().get_home_page_data().get("companies", [])
        except ShareHubError:
            return Response(
                {"detail": "Market data is temporarily unavailable."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        market_data = {
            company.get("symbol"): company
            for company in companies
            if company.get("symbol")
        }
        result = []
        for holding in holdings:
            company = market_data.get(holding.symbol, {})
            current_price = company.get("ltp")
            current_price = (
                Decimal("0") if current_price is None else Decimal(str(current_price))
            )
            quantity = Decimal(holding.quantity)
            market_value = quantity * current_price
            cost_value = quantity * holding.average_buy_price
            result.append(
                {
                    "symbol": holding.symbol,
                    "company_name": holding.company_name,
                    "quantity": holding.quantity,
                    "average_buy_price": holding.average_buy_price,
                    "current_price": current_price,
                    "market_value": market_value,
                    "unrealized_profit_loss": market_value - cost_value,
                }
            )

        return Response(PortfolioHoldingSerializer(result, many=True).data)


class OrderListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(tags=["Trading"], responses=OrderSerializer(many=True))
    def get(self, request):
        orders = Order.objects.filter(user=request.user)
        return Response(OrderSerializer(orders, many=True).data)

    @extend_schema(
        tags=["Trading"], request=OrderCreateSerializer, responses=OrderSerializer
    )
    def post(self, request):
        serializer = OrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = TradingService.execute_order(
                request.user,
                serializer.validated_data["symbol"],
                serializer.validated_data["side"],
                serializer.validated_data["quantity"],
            )
        except MarketUnavailableError:
            return Response(
                {"detail": "Market data is temporarily unavailable."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except MarketClosedError:
            return Response(
                {"detail": "Market is currently closed."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        order, trade, rejection_reason = result
        if rejection_reason:
            return Response(
                {"detail": rejection_reason, "order": OrderSerializer(order).data},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)


class TradeListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(tags=["Trading"], responses=TradeSerializer(many=True))
    def get(self, request):
        trades = Trade.objects.filter(user=request.user)
        return Response(TradeSerializer(trades, many=True).data)
