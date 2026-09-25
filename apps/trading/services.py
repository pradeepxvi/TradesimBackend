from decimal import Decimal

from django.db import transaction

from apps.market.clients.sharehub import ShareHubClient, ShareHubError

from .models import Holding, Order, Trade, Wallet


class TradingError(Exception):
    """A user-safe trading validation error."""


class MarketUnavailableError(TradingError):
    pass


class MarketClosedError(TradingError):
    pass


class TradingService:
    @staticmethod
    def execute_order(user, symbol, side, quantity):
        with transaction.atomic():
            market_client = ShareHubClient()
            try:
                market_status = market_client.get_market_status()
                market_data = market_client.get_home_page_data().get("companies", [])
            except ShareHubError as error:
                raise MarketUnavailableError from error

            if str(market_status.get("status", "")).upper() != "OPEN":
                raise MarketClosedError

            company = next(
                (
                    item
                    for item in market_data
                    if item.get("symbol", "").upper() == symbol
                ),
                None,
            )
            if not company or company.get("ltp") is None:
                raise MarketUnavailableError

            price = Decimal(str(company["ltp"]))
            total_amount = price * Decimal(quantity)
            wallet = Wallet.objects.select_for_update().get(user=user)
            holding = (
                Holding.objects.select_for_update()
                .filter(user=user, symbol=symbol)
                .first()
            )

            if side == Order.BUY:
                if wallet.virtual_balance < total_amount:
                    return TradingService._create_rejected_order(
                        user, symbol, side, quantity, price, total_amount
                    )
                wallet.virtual_balance -= total_amount
                wallet.save(update_fields=["virtual_balance", "updated_at"])
                if holding:
                    combined_cost = (
                        Decimal(holding.quantity) * holding.average_buy_price
                    ) + total_amount
                    holding.quantity += quantity
                    holding.average_buy_price = combined_cost / Decimal(
                        holding.quantity
                    )
                    holding.company_name = company.get("name") or holding.company_name
                    holding.save(
                        update_fields=[
                            "quantity",
                            "average_buy_price",
                            "company_name",
                            "updated_at",
                        ]
                    )
                else:
                    holding = Holding.objects.create(
                        user=user,
                        symbol=symbol,
                        company_name=company.get("name", symbol),
                        quantity=quantity,
                        average_buy_price=price,
                    )
            else:
                if not holding or holding.quantity < quantity:
                    return TradingService._create_rejected_order(
                        user, symbol, side, quantity, price, total_amount
                    )
                wallet.virtual_balance += total_amount
                wallet.save(update_fields=["virtual_balance", "updated_at"])
                holding.quantity -= quantity
                if holding.quantity == 0:
                    holding.delete()
                else:
                    holding.save(update_fields=["quantity", "updated_at"])

            order = Order.objects.create(
                user=user,
                symbol=symbol,
                side=side,
                quantity=quantity,
                price=price,
                total_amount=total_amount,
                status=Order.EXECUTED,
            )
            trade = Trade.objects.create(
                order=order,
                user=user,
                symbol=symbol,
                side=side,
                quantity=quantity,
                price=price,
                total_amount=total_amount,
            )
            return order, trade, None

    @staticmethod
    def _create_rejected_order(user, symbol, side, quantity, price, total_amount):
        return (
            Order.objects.create(
                user=user,
                symbol=symbol,
                side=side,
                quantity=quantity,
                price=price,
                total_amount=total_amount,
                status=Order.REJECTED,
            ),
            None,
            (
                "Insufficient wallet balance."
                if side == Order.BUY
                else "Insufficient holdings."
            ),
        )
