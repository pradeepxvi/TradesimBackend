from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field

from apps.market.clients.sharehub import InvalidSymbolError, ShareHubClient

from .models import WatchlistItem


class WatchlistItemSerializer(serializers.ModelSerializer):
    market = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = WatchlistItem
        fields = ("id", "symbol", "created_at", "market")
        read_only_fields = ("id", "created_at", "market")

    def validate_symbol(self, value):
        try:
            return ShareHubClient._validate_symbol(value)
        except InvalidSymbolError as error:
            raise serializers.ValidationError("Invalid market symbol.") from error

    @extend_schema_field(serializers.DictField())
    def get_market(self, obj):
        return self.context.get("market_data", {}).get(obj.symbol, {})
