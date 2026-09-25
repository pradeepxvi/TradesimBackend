from rest_framework import serializers


class MarketStatusSerializer(serializers.Serializer):
    status = serializers.CharField(allow_blank=True)
    time = serializers.CharField(required=False, allow_null=True, allow_blank=True)


class MarketSummarySerializer(serializers.Serializer):
    total_turnover = serializers.DecimalField(
        max_digits=24, decimal_places=4, required=False, allow_null=True
    )
    total_transactions = serializers.IntegerField(required=False, allow_null=True)
    total_volume = serializers.IntegerField(required=False, allow_null=True)
    advances = serializers.IntegerField(required=False, allow_null=True)
    declines = serializers.IntegerField(required=False, allow_null=True)
    unchanged = serializers.IntegerField(required=False, allow_null=True)


class StockSummarySerializer(serializers.Serializer):
    total_companies = serializers.IntegerField(required=False, allow_null=True)
    total_traded = serializers.IntegerField(required=False, allow_null=True)
    total_turnover = serializers.DecimalField(
        max_digits=24, decimal_places=4, required=False, allow_null=True
    )
    total_transactions = serializers.IntegerField(required=False, allow_null=True)


class CompanySerializer(serializers.Serializer):
    symbol = serializers.CharField()
    name = serializers.CharField(required=False, allow_blank=True)
    sector = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    ltp = serializers.DecimalField(
        max_digits=24, decimal_places=4, required=False, allow_null=True
    )
    change = serializers.DecimalField(
        max_digits=24, decimal_places=4, required=False, allow_null=True
    )
    change_percent = serializers.DecimalField(
        max_digits=12, decimal_places=4, required=False, allow_null=True
    )


class CompanyQuoteSerializer(CompanySerializer):
    open = serializers.DecimalField(
        max_digits=24, decimal_places=4, required=False, allow_null=True
    )
    high = serializers.DecimalField(
        max_digits=24, decimal_places=4, required=False, allow_null=True
    )
    low = serializers.DecimalField(
        max_digits=24, decimal_places=4, required=False, allow_null=True
    )
    volume = serializers.IntegerField(required=False, allow_null=True)
    turnover = serializers.DecimalField(
        max_digits=24, decimal_places=4, required=False, allow_null=True
    )
    transactions = serializers.IntegerField(required=False, allow_null=True)
    previous_close = serializers.DecimalField(
        max_digits=24, decimal_places=4, required=False, allow_null=True
    )
    updated_at = serializers.CharField(
        required=False, allow_null=True, allow_blank=True
    )


class CandleSerializer(serializers.Serializer):
    date = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    open = serializers.DecimalField(
        max_digits=24, decimal_places=4, required=False, allow_null=True
    )
    high = serializers.DecimalField(
        max_digits=24, decimal_places=4, required=False, allow_null=True
    )
    low = serializers.DecimalField(
        max_digits=24, decimal_places=4, required=False, allow_null=True
    )
    close = serializers.DecimalField(
        max_digits=24, decimal_places=4, required=False, allow_null=True
    )
    volume = serializers.DecimalField(
        max_digits=30, decimal_places=4, required=False, allow_null=True
    )


class IndexSerializer(serializers.Serializer):
    symbol = serializers.CharField(required=False, allow_blank=True)
    name = serializers.CharField(required=False, allow_blank=True)
    ltp = serializers.DecimalField(
        max_digits=24, decimal_places=4, required=False, allow_null=True
    )
    change = serializers.DecimalField(
        max_digits=24, decimal_places=4, required=False, allow_null=True
    )
    change_percent = serializers.DecimalField(
        max_digits=12, decimal_places=4, required=False, allow_null=True
    )


class GainerLoserSerializer(CompanySerializer):
    pass


class ChangeSummarySerializer(serializers.Serializer):
    name = serializers.CharField(required=False, allow_blank=True)
    change = serializers.DecimalField(
        max_digits=24, decimal_places=4, required=False, allow_null=True
    )
    change_percent = serializers.DecimalField(
        max_digits=12, decimal_places=4, required=False, allow_null=True
    )
    date = serializers.CharField(required=False, allow_null=True, allow_blank=True)


class MarketOverviewSerializer(serializers.Serializer):
    market_status = MarketStatusSerializer(required=False)
    market_summary = MarketSummarySerializer(required=False)
    stock_summary = StockSummarySerializer(required=False)
    indices = IndexSerializer(many=True, required=False)
    top_gainers = GainerLoserSerializer(many=True, required=False)
    top_losers = GainerLoserSerializer(many=True, required=False)
    top_turnover = CompanySerializer(many=True, required=False)
    top_traded_shares = CompanySerializer(many=True, required=False)
    top_transactions = CompanySerializer(many=True, required=False)
