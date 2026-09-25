from unittest.mock import patch

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from apps.market.clients.sharehub import ShareHubClient

from .models import WatchlistItem

User = get_user_model()


class WatchlistAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user("one@example.com", "StrongPass123!")
        self.user.is_verified = True
        self.user.save(update_fields=["is_verified"])
        self.other_user = User.objects.create_user("two@example.com", "StrongPass123!")
        self.other_user.is_verified = True
        self.other_user.save(update_fields=["is_verified"])

        patcher = patch("apps.watchlist.views.ShareHubClient")
        self.addCleanup(patcher.stop)
        self.client_class = patcher.start()
        self.market_client = self.client_class.return_value
        self.client_class._validate_symbol.side_effect = ShareHubClient._validate_symbol
        self.market_client.get_home_page_data.return_value = {
            "companies": [
                {
                    "symbol": "GBIME",
                    "name": "Global IME Bank",
                    "sector": "Commercial Banks",
                    "ltp": 250,
                    "change": 2,
                    "change_percent": 0.8,
                },
                {"symbol": "NABIL", "name": "Nabil Bank", "ltp": 500},
            ]
        }

    def authenticate(self, user=None):
        self.client.force_authenticate(user=user or self.user)

    def test_anonymous_user_is_rejected(self):
        response = self.client.get("/api/v1/watchlist/")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authenticated_user_can_create_lowercase_symbol(self):
        self.authenticate()

        response = self.client.post(
            "/api/v1/watchlist/",
            {"symbol": "gbime"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["symbol"], "GBIME")
        self.assertEqual(WatchlistItem.objects.get().user, self.user)

    def test_duplicate_symbol_is_rejected(self):
        self.authenticate()
        WatchlistItem.objects.create(user=self.user, symbol="GBIME")

        response = self.client.post(
            "/api/v1/watchlist/",
            {"symbol": "gbime"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_symbol_is_rejected(self):
        self.authenticate()

        response = self.client.post(
            "/api/v1/watchlist/",
            {"symbol": "A/B"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unknown_company_is_rejected(self):
        self.authenticate()

        response = self.client.post(
            "/api/v1/watchlist/",
            {"symbol": "UNKNOWN"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_authenticated_user_can_list_with_market_data(self):
        WatchlistItem.objects.create(user=self.user, symbol="GBIME")
        self.authenticate()

        response = self.client.get("/api/v1/watchlist/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data[0]["symbol"], "GBIME")
        self.assertEqual(response.data[0]["market"]["ltp"], 250)

    def test_user_cannot_see_another_users_watchlist(self):
        WatchlistItem.objects.create(user=self.other_user, symbol="GBIME")
        self.authenticate(self.user)

        response = self.client.get("/api/v1/watchlist/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])

    def test_authenticated_user_can_delete_symbol(self):
        WatchlistItem.objects.create(user=self.user, symbol="GBIME")
        self.authenticate()

        response = self.client.delete("/api/v1/watchlist/gbime/")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(WatchlistItem.objects.filter(user=self.user).exists())

    def test_user_cannot_delete_another_users_symbol(self):
        WatchlistItem.objects.create(user=self.other_user, symbol="GBIME")
        self.authenticate(self.user)

        response = self.client.delete("/api/v1/watchlist/GBIME/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(
            WatchlistItem.objects.filter(user=self.other_user, symbol="GBIME").exists()
        )
