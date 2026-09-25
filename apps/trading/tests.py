from decimal import Decimal
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APITestCase

from apps.market.clients.sharehub import ShareHubError

from .models import Holding, Order, Trade, Wallet

User = get_user_model()


class WalletSignalTests(TestCase):
    def test_verified_user_gets_wallet_with_initial_balance(self):
        user = User.objects.create_user("verified@example.com", "StrongPass123!")
        user.is_verified = True
        user.save(update_fields=["is_verified"])

        wallet = Wallet.objects.get(user=user)

        self.assertEqual(wallet.virtual_balance, settings.INITIAL_VIRTUAL_BALANCE)
        self.assertEqual(Wallet.objects.filter(user=user).count(), 1)


class WalletPortfolioAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user("trader@example.com", "StrongPass123!")
        self.user.is_verified = True
        self.user.save(update_fields=["is_verified"])
        self.other_user = User.objects.create_user(
            "other@example.com", "StrongPass123!"
        )
        self.other_user.is_verified = True
        self.other_user.save(update_fields=["is_verified"])

    def test_anonymous_user_cannot_view_wallet_or_portfolio(self):
        self.assertEqual(self.client.get("/api/v1/trading/wallet/").status_code, 401)
        self.assertEqual(self.client.get("/api/v1/trading/portfolio/").status_code, 401)

    def test_authenticated_user_can_view_wallet(self):
        self.client.force_authenticate(self.user)

        response = self.client.get("/api/v1/trading/wallet/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["virtual_balance"], "1000000.00")

    @patch("apps.trading.views.ShareHubClient")
    def test_portfolio_uses_market_price_and_decimal_calculation(self, client_class):
        client_class.return_value.get_home_page_data.return_value = {
            "companies": [
                {
                    "symbol": "GBIME",
                    "name": "Global IME Bank",
                    "ltp": "125.50",
                }
            ]
        }
        Holding.objects.create(
            user=self.user,
            symbol="gbime",
            company_name="Global IME Bank",
            quantity=10,
            average_buy_price=Decimal("100.00"),
        )
        self.client.force_authenticate(self.user)

        response = self.client.get("/api/v1/trading/portfolio/")

        self.assertEqual(response.status_code, 200)
        holding = response.data[0]
        self.assertEqual(holding["current_price"], "125.5000")
        self.assertEqual(holding["market_value"], "1255.0000")
        self.assertEqual(holding["unrealized_profit_loss"], "255.0000")
        client_class.return_value.get_home_page_data.assert_called_once_with()

    @patch("apps.trading.views.ShareHubClient")
    def test_portfolio_is_limited_to_authenticated_user(self, client_class):
        client_class.return_value.get_home_page_data.return_value = {"companies": []}
        Holding.objects.create(
            user=self.other_user,
            symbol="GBIME",
            company_name="Global IME Bank",
            quantity=10,
            average_buy_price=Decimal("100.00"),
        )
        self.client.force_authenticate(self.user)

        response = self.client.get("/api/v1/trading/portfolio/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])


class TradingEngineAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user("buyer@example.com", "StrongPass123!")
        self.user.is_verified = True
        self.user.save(update_fields=["is_verified"])
        self.other_user = User.objects.create_user(
            "seller@example.com", "StrongPass123!"
        )
        self.other_user.is_verified = True
        self.other_user.save(update_fields=["is_verified"])
        self.client.force_authenticate(self.user)

    def market_client(self, price="100.00", status="OPEN"):
        patcher = patch("apps.trading.services.ShareHubClient")
        self.addCleanup(patcher.stop)
        client_class = patcher.start()
        client_class.return_value.get_market_status.return_value = {"status": status}
        client_class.return_value.get_home_page_data.return_value = {
            "companies": [{"symbol": "GBIME", "name": "Global IME Bank", "ltp": price}]
        }
        return client_class

    def test_successful_buy_updates_wallet_holding_order_and_trade(self):
        self.market_client("100.00")

        response = self.client.post(
            "/api/v1/trading/orders/",
            {"symbol": "gbime", "side": "BUY", "quantity": 10},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            Wallet.objects.get(user=self.user).virtual_balance, Decimal("999000.00")
        )
        holding = Holding.objects.get(user=self.user, symbol="GBIME")
        self.assertEqual(holding.quantity, 10)
        self.assertEqual(holding.average_buy_price, Decimal("100.0000"))
        self.assertEqual(
            Order.objects.filter(user=self.user, status=Order.EXECUTED).count(), 1
        )
        self.assertEqual(Trade.objects.filter(user=self.user).count(), 1)

    def test_multiple_buys_use_decimal_average_price(self):
        self.market_client("100.00")
        self.client.post(
            "/api/v1/trading/orders/",
            {"symbol": "GBIME", "side": "BUY", "quantity": 10},
            format="json",
        )
        patch.stopall()
        self.market_client("120.00")

        response = self.client.post(
            "/api/v1/trading/orders/",
            {"symbol": "GBIME", "side": "BUY", "quantity": 10},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            Holding.objects.get(user=self.user, symbol="GBIME").average_buy_price,
            Decimal("110.0000"),
        )

    def test_insufficient_balance_rejects_without_mutating_wallet(self):
        self.market_client("1000001.00")

        response = self.client.post(
            "/api/v1/trading/orders/",
            {"symbol": "GBIME", "side": "BUY", "quantity": 1},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Insufficient wallet balance", response.data["detail"])
        self.assertEqual(Order.objects.get(user=self.user).status, Order.REJECTED)
        self.assertEqual(
            Wallet.objects.get(user=self.user).virtual_balance, Decimal("1000000.00")
        )
        self.assertFalse(Holding.objects.filter(user=self.user).exists())

    def test_invalid_quantity_and_symbol_are_rejected(self):
        self.market_client()
        for payload in (
            {"symbol": "GBIME", "side": "BUY", "quantity": 0},
            {"symbol": "GBIME", "side": "BUY", "quantity": -1},
            {"symbol": "A/B", "side": "BUY", "quantity": 1},
            {"symbol": "GBIME", "side": "HOLD", "quantity": 1},
        ):
            response = self.client.post(
                "/api/v1/trading/orders/", payload, format="json"
            )
            self.assertEqual(response.status_code, 400)

    def test_market_closed_and_unavailable_are_rejected(self):
        self.market_client(status="CLOSE")
        response = self.client.post(
            "/api/v1/trading/orders/",
            {"symbol": "GBIME", "side": "BUY", "quantity": 1},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("closed", response.data["detail"])

        patch.stopall()
        patcher = patch("apps.trading.services.ShareHubClient")
        self.addCleanup(patcher.stop)
        client_class = patcher.start()
        client_class.return_value.get_market_status.side_effect = ShareHubError()
        response = self.client.post(
            "/api/v1/trading/orders/",
            {"symbol": "GBIME", "side": "BUY", "quantity": 1},
            format="json",
        )
        self.assertEqual(response.status_code, 503)

    def test_successful_sell_updates_wallet_and_holding(self):
        self.market_client("100.00")
        Holding.objects.create(
            user=self.user,
            symbol="GBIME",
            company_name="Global IME Bank",
            quantity=10,
            average_buy_price=Decimal("80.00"),
        )
        response = self.client.post(
            "/api/v1/trading/orders/",
            {"symbol": "GBIME", "side": "SELL", "quantity": 4},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            Wallet.objects.get(user=self.user).virtual_balance, Decimal("1000400.00")
        )
        holding = Holding.objects.get(user=self.user, symbol="GBIME")
        self.assertEqual(holding.quantity, 6)
        self.assertEqual(holding.average_buy_price, Decimal("80.00"))

    def test_complete_sell_removes_holding_and_excess_sell_is_rejected(self):
        self.market_client("100.00")
        Holding.objects.create(
            user=self.user,
            symbol="GBIME",
            company_name="Global IME Bank",
            quantity=10,
            average_buy_price=Decimal("80.00"),
        )
        response = self.client.post(
            "/api/v1/trading/orders/",
            {"symbol": "GBIME", "side": "SELL", "quantity": 11},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertTrue(Holding.objects.filter(user=self.user, symbol="GBIME").exists())

        response = self.client.post(
            "/api/v1/trading/orders/",
            {"symbol": "GBIME", "side": "SELL", "quantity": 10},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertFalse(
            Holding.objects.filter(user=self.user, symbol="GBIME").exists()
        )

    def test_order_and_trade_history_are_user_scoped(self):
        order = Order.objects.create(
            user=self.other_user,
            symbol="GBIME",
            side=Order.BUY,
            quantity=1,
            price=Decimal("100.00"),
            total_amount=Decimal("100.00"),
            status=Order.EXECUTED,
        )
        Trade.objects.create(
            order=order,
            user=self.other_user,
            symbol="GBIME",
            side=Order.BUY,
            quantity=1,
            price=Decimal("100.00"),
            total_amount=Decimal("100.00"),
        )

        self.assertEqual(self.client.get("/api/v1/trading/orders/").data, [])
        self.assertEqual(self.client.get("/api/v1/trading/trades/").data, [])

    @patch("apps.trading.services.Holding.objects.create")
    def test_execution_failure_rolls_back_wallet_and_holding(self, create_holding):
        self.market_client("100.00")
        create_holding.side_effect = RuntimeError("forced failure")
        wallet_before = Wallet.objects.get(user=self.user).virtual_balance

        with self.assertRaises(RuntimeError):
            self.client.post(
                "/api/v1/trading/orders/",
                {"symbol": "GBIME", "side": "BUY", "quantity": 1},
                format="json",
            )

        self.assertEqual(
            Wallet.objects.get(user=self.user).virtual_balance, wallet_before
        )
        self.assertFalse(Holding.objects.filter(user=self.user).exists())
        self.assertFalse(Order.objects.filter(user=self.user).exists())
