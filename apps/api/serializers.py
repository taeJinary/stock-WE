from rest_framework import serializers


class MarketSummaryItemSerializer(serializers.Serializer):
    label = serializers.CharField()
    price = serializers.CharField()
    change_rate = serializers.FloatField()


class TopInterestStockSerializer(serializers.Serializer):
    symbol = serializers.CharField()
    name = serializers.CharField()
    market = serializers.CharField()
    sector = serializers.CharField()
    total_mentions = serializers.IntegerField()


class InterestAnomalySerializer(serializers.Serializer):
    symbol = serializers.CharField()
    name = serializers.CharField()
    recent_mentions = serializers.IntegerField()
    expected_mentions = serializers.IntegerField()
    baseline_hourly_avg = serializers.FloatField()
    surge_ratio = serializers.FloatField()
    z_score = serializers.FloatField()
    severity = serializers.CharField()


class StockSummarySerializer(serializers.Serializer):
    class StockMetaSerializer(serializers.Serializer):
        symbol = serializers.CharField()
        name = serializers.CharField()
        market = serializers.CharField()
        sector = serializers.CharField()

    class PriceSnapshotSerializer(serializers.Serializer):
        traded_at = serializers.DateField()
        open_price = serializers.FloatField()
        high_price = serializers.FloatField()
        low_price = serializers.FloatField()
        close_price = serializers.FloatField()
        volume = serializers.IntegerField()

    class PricePointSerializer(serializers.Serializer):
        date = serializers.CharField()
        close = serializers.FloatField()

    class InterestPointSerializer(serializers.Serializer):
        date = serializers.CharField()
        mentions = serializers.IntegerField()

    class NewsItemSerializer(serializers.Serializer):
        title = serializers.CharField()
        url = serializers.URLField()
        publisher = serializers.CharField(allow_blank=True)
        published_at = serializers.DateTimeField(allow_null=True)

    stock = StockMetaSerializer()
    latest_price = PriceSnapshotSerializer(allow_null=True)
    price_chart_data = PricePointSerializer(many=True)
    interest_chart_data = InterestPointSerializer(many=True)
    news_items = NewsItemSerializer(many=True)
    stock_anomaly = InterestAnomalySerializer(allow_null=True)
