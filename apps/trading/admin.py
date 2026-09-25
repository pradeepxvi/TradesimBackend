from django.contrib import admin

from .models import Holding, Order, Trade, Wallet


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ("user", "virtual_balance", "updated_at")
    search_fields = ("user__email",)


@admin.register(Holding)
class HoldingAdmin(admin.ModelAdmin):
    list_display = ("user", "symbol", "quantity", "average_buy_price")
    search_fields = ("user__email", "symbol", "company_name")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("user", "symbol", "side", "quantity", "status", "created_at")
    list_filter = ("side", "status")
    search_fields = ("user__email", "symbol")
    readonly_fields = (
        "user",
        "symbol",
        "side",
        "quantity",
        "price",
        "total_amount",
        "status",
        "created_at",
    )


@admin.register(Trade)
class TradeAdmin(admin.ModelAdmin):
    list_display = ("user", "symbol", "side", "quantity", "price", "executed_at")
    list_filter = ("side",)
    search_fields = ("user__email", "symbol")
    readonly_fields = (
        "order",
        "user",
        "symbol",
        "side",
        "quantity",
        "price",
        "total_amount",
        "executed_at",
    )
