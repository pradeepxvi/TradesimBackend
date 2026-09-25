from django.conf import settings
from django.db import models


class Wallet(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="wallet",
    )
    virtual_balance = models.DecimalField(
        max_digits=20,
        decimal_places=2,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Wallet for {self.user.email}"


class Holding(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="holdings",
    )
    symbol = models.CharField(max_length=32)
    company_name = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField()
    average_buy_price = models.DecimalField(max_digits=20, decimal_places=4)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("user", "symbol"),
                name="unique_holding_user_symbol",
            )
        ]
        ordering = ("symbol",)

    def save(self, *args, **kwargs):
        self.symbol = self.symbol.strip().upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.email}: {self.symbol} ({self.quantity})"


class Order(models.Model):
    BUY = "BUY"
    SELL = "SELL"
    SIDE_CHOICES = ((BUY, "Buy"), (SELL, "Sell"))
    EXECUTED = "EXECUTED"
    REJECTED = "REJECTED"
    STATUS_CHOICES = ((EXECUTED, "Executed"), (REJECTED, "Rejected"))

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="orders",
    )
    symbol = models.CharField(max_length=32)
    side = models.CharField(max_length=4, choices=SIDE_CHOICES)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=20, decimal_places=4)
    total_amount = models.DecimalField(max_digits=24, decimal_places=4)
    status = models.CharField(max_length=9, choices=STATUS_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.side} {self.quantity} {self.symbol} ({self.status})"


class Trade(models.Model):
    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        related_name="trade",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="trades",
    )
    symbol = models.CharField(max_length=32)
    side = models.CharField(max_length=4)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=20, decimal_places=4)
    total_amount = models.DecimalField(max_digits=24, decimal_places=4)
    executed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-executed_at",)

    def __str__(self):
        return f"Trade {self.side} {self.quantity} {self.symbol}"
