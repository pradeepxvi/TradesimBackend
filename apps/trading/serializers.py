from rest_framework import serializers

from apps.market.clients.sharehub import InvalidSymbolError, ShareHubClient

from .models import Holding, Order, Trade, Wallet


class WalletSerializer(serializers.ModelSerializer):
    class Meta:
        model = Wallet
        fields = ("virtual_balance",)
        read_only_fields = ("virtual_balance",)


class PortfolioHoldingSerializer(serializers.ModelSerializer):
    current_price = serializers.DecimalField(
        max_digits=24, decimal_places=4, read_only=True
    )
    market_value = serializers.DecimalField(
        max_digits=30, decimal_places=4, read_only=True
    )
    unrealized_profit_loss = serializers.DecimalField(
        max_digits=30, decimal_places=4, read_only=True
    )

    class Meta:
        model = Holding
        fields = (
            "symbol",
            "company_name",
            "quantity",
            "average_buy_price",
            "current_price",
            "market_value",
            "unrealized_profit_loss",
        )
        read_only_fields = fields


class OrderCreateSerializer(serializers.Serializer):
    symbol = serializers.CharField(max_length=32)
    side = serializers.ChoiceField(choices=("BUY", "SELL"))
    quantity = serializers.IntegerField(min_value=1)

    def validate_symbol(self, value):
        try:
            return ShareHubClient._validate_symbol(value)
        except InvalidSymbolError as error:
            raise serializers.ValidationError("Invalid market symbol.") from error


class OrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = (
            "id",
            "symbol",
            "side",
            "quantity",
            "price",
            "total_amount",
            "status",
            "created_at",
        )
        read_only_fields = fields


class TradeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Trade
        fields = (
            "id",
            "order",
            "symbol",
            "side",
            "quantity",
            "price",
            "total_amount",
            "executed_at",
        )
        read_only_fields = fields
