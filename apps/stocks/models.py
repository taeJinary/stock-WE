from django.db import models


class Stock(models.Model):
    class Market(models.TextChoices):
        KOREA = "KR", "Korea"
        USA = "US", "USA"

    symbol = models.CharField(max_length=16, unique=True)
    name = models.CharField(max_length=128)
    market = models.CharField(max_length=2, choices=Market.choices)
    sector = models.CharField(max_length=64, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["symbol"]

    def __str__(self):
        return f"{self.symbol} ({self.market})"


class Price(models.Model):
    stock = models.ForeignKey(Stock, related_name="prices", on_delete=models.CASCADE)
    traded_at = models.DateField()
    open_price = models.DecimalField(max_digits=14, decimal_places=2)
    high_price = models.DecimalField(max_digits=14, decimal_places=2)
    low_price = models.DecimalField(max_digits=14, decimal_places=2)
    close_price = models.DecimalField(max_digits=14, decimal_places=2)
    volume = models.BigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-traded_at", "-id"]
        unique_together = ("stock", "traded_at")
        indexes = [models.Index(fields=["traded_at"])]


class Interest(models.Model):
    class Source(models.TextChoices):
        REDDIT = "reddit", "Reddit"
        NAVER = "naver", "Naver"
        NEWS = "news", "News"

    stock = models.ForeignKey(Stock, related_name="interest_records", on_delete=models.CASCADE)
    source = models.CharField(max_length=16, choices=Source.choices)
    recorded_at = models.DateTimeField()
    mentions = models.PositiveIntegerField(default=0)
    sentiment_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        blank=True,
        null=True,
    )
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-recorded_at", "-id"]
        indexes = [models.Index(fields=["recorded_at", "source"])]
