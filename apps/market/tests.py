from unittest.mock import Mock
from unittest.mock import patch

import requests
from django.core.cache import cache
from django.test import SimpleTestCase
from rest_framework.test import APITestCase

from .clients.sharehub import (
    InvalidSymbolError,
    ShareHubClient,
    ShareHubError,
)


class ShareHubClientTests(SimpleTestCase):
    base_url = "https://sharehubnepal.com"

    def setUp(self):
        self.session = Mock()
        self.client = ShareHubClient(base_url=self.base_url, session=self.session)

    def response(self, payload):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = payload
        self.session.get.return_value = response
        return response

    def test_successful_company_candle_response_is_normalized(self):
        self.response(
            {
                "data": [
                    {
                        "tradingDate": "2026-09-18",
                        "openPrice": 100,
                        "highPrice": 110,
                        "lowPrice": 95,
                        "lastTradedPrice": 105,
                        "totalTradeQuantity": 500,
                        "unneededField": "ignored",
                    }
                ]
            }
        )

        result = self.client.get_company_candles(" gbime ")

        self.assertEqual(result[0]["date"], "2026-09-18")
        self.assertEqual(result[0]["close"], 105)
        self.assertEqual(result[0]["volume"], 500)
        self.assertNotIn("unneededField", result[0])
        self.session.get.assert_called_once_with(
            f"{self.base_url}/live/api/v1/daily-graph/company/candle/GBIME",
            timeout=10,
        )

    def test_quote_fields_are_normalized_and_missing_fields_ignored(self):
        self.response(
            {
                "data": [
                    {
                        "name": "3 Days",
                        "change": -19,
                        "changePercent": -2.51,
                        "unknown": "ignored",
                    }
                ]
            }
        )

        result = self.client.get_change_summary("matri")

        self.assertEqual(
            result,
            [{"name": "3 Days", "change": -19, "change_percent": -2.51}],
        )

    def test_market_status_is_sanitized(self):
        self.response(
            {
                "data": {
                    "marketStatus": "OPEN",
                    "isOpen": True,
                    "secret": "ignored",
                }
            }
        )

        self.assertEqual(
            self.client.get_market_status(),
            {"status": "OPEN", "is_open": True},
        )

    def test_live_market_status_shape_is_normalized(self):
        self.response(
            {
                "isOpen": "CLOSE",
                "asOf": "2026-09-18T15:00:00",
                "id": 80,
            }
        )

        result = self.client.get_market_status()

        self.assertEqual(
            result,
            {
                "status": "CLOSE",
                "is_open": "CLOSE",
                "updated_at": "2026-09-18T15:00:00",
            },
        )

    def test_live_homepage_shape_includes_companies_and_summaries(self):
        self.response(
            {
                "marketStatus": {"status": "CLOSE", "time": "2026-09-18T15:00:00Z"},
                "marketSummary": [
                    {"name": "Total Turnover Rs:", "value": 1000},
                    {"name": "Total Traded Shares", "value": 200},
                ],
                "liveCompanyData": [
                    {
                        "symbol": "GBIME",
                        "securityName": "Global IME Bank",
                        "lastTradedPrice": 250,
                        "internalId": "ignored",
                    }
                ],
            }
        )

        result = self.client.get_home_page_data()

        self.assertEqual(result["market_status"]["status"], "CLOSE")
        self.assertEqual(result["market_summary"]["total_volume"], 200)
        self.assertEqual(result["companies"][0]["symbol"], "GBIME")
        self.assertNotIn("internalId", result["companies"][0])

    def test_top_gainers_and_losers_are_normalized(self):
        self.response(
            {
                "data": {
                    "topGainers": [{"symbol": "AAA", "securityName": "A"}],
                    "topLosers": [{"symbol": "BBB", "percentageChange": -2}],
                }
            }
        )

        result = self.client.get_top_gainers_losers()

        self.assertEqual(result["gainers"][0]["name"], "A")
        self.assertEqual(result["losers"][0]["change_percent"], -2)

    def test_top_gainers_and_losers_content_is_split_by_change(self):
        self.response(
            {
                "success": True,
                "data": {
                    "content": [
                        {
                            "symbol": "AAA",
                            "name": "A",
                            "pointChange": 10,
                            "percentChange": 5,
                            "lastTradedPrice": 100,
                            "iconUrl": "ignored",
                        },
                        {
                            "symbol": "BBB",
                            "name": "B",
                            "pointChange": -10,
                            "percentChange": -5,
                            "lastTradedPrice": 80,
                            "iconUrl": "ignored",
                        },
                    ]
                },
            }
        )

        result = self.client.get_top_gainers_losers()

        self.assertEqual(result["gainers"][0]["symbol"], "AAA")
        self.assertEqual(result["gainers"][0]["change"], 10)
        self.assertEqual(result["losers"][0]["symbol"], "BBB")
        self.assertEqual(result["losers"][0]["change_percent"], -5)
        self.assertNotIn("iconUrl", result["gainers"][0])

    def test_top_losers_fall_back_to_homepage_when_content_has_only_gainers(self):
        first_response = Mock()
        first_response.raise_for_status.return_value = None
        first_response.json.return_value = {
            "data": {
                "content": [
                    {
                        "symbol": "AAA",
                        "name": "A",
                        "percentChange": 5,
                    }
                ]
            }
        }
        second_response = Mock()
        second_response.raise_for_status.return_value = None
        second_response.json.return_value = {
            "topLosers": [{"symbol": "BBB", "name": "B", "percentChange": -5}]
        }
        self.session.get.side_effect = [first_response, second_response]

        result = self.client.get_top_gainers_losers()

        self.assertEqual(result["gainers"][0]["symbol"], "AAA")
        self.assertEqual(result["losers"][0]["symbol"], "BBB")

    def test_timeout_is_wrapped(self):
        self.session.get.side_effect = requests.Timeout()

        with self.assertRaises(ShareHubError):
            self.client.get_market_status()

    def test_connection_failure_is_wrapped(self):
        self.session.get.side_effect = requests.ConnectionError()

        with self.assertRaises(ShareHubError):
            self.client.get_market_status()

    def test_http_error_is_wrapped(self):
        response = Mock()
        response.raise_for_status.side_effect = requests.HTTPError("500")
        self.session.get.return_value = response

        with self.assertRaises(ShareHubError):
            self.client.get_market_status()

    def test_invalid_json_is_wrapped(self):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.side_effect = ValueError("not json")
        self.session.get.return_value = response

        with self.assertRaises(ShareHubError):
            self.client.get_market_status()

    def test_missing_fields_return_clean_empty_shapes(self):
        self.response({"data": {"unrelated": "value"}})

        self.assertEqual(self.client.get_market_status(), {})
        self.assertEqual(self.client.get_change_summary("AAA"), [])

    def test_invalid_symbols_are_rejected_before_request(self):
        for symbol in ("", "A/B", "https://example.com", 123, None):
            with self.subTest(symbol=symbol):
                with self.assertRaises(InvalidSymbolError):
                    self.client.get_company_candles(symbol)

        self.session.get.assert_not_called()


class MarketAPITests(APITestCase):
    def setUp(self):
        cache.clear()
        patcher = patch("apps.market.views.ShareHubClient")
        self.addCleanup(patcher.stop)
        self.client_class = patcher.start()
        self.sharehub = self.client_class.return_value
        self.client_class._validate_symbol.side_effect = ShareHubClient._validate_symbol

    def test_market_status(self):
        self.sharehub.get_market_status.return_value = {
            "status": "OPEN",
            "updated_at": "2026-09-18T10:00:00+05:45",
            "secret": "ignored",
        }

        response = self.client.get("/api/v1/market/status/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data,
            {"status": "OPEN", "time": "2026-09-18T10:00:00+05:45"},
        )
        self.assertNotIn("secret", response.data)

    def test_market_overview_is_sanitized(self):
        self.sharehub.get_home_page_data.return_value = {
            "market_status": {"status": "OPEN", "updated_at": "now"},
            "market_summary": {"total_turnover": 1000, "internal": "ignored"},
            "stock_summary": {"total_companies": 200},
            "indices": [{"symbol": "NEPSE", "ltp": 2000, "raw": "ignored"}],
            "top_gainers": [{"symbol": "AAA", "name": "A", "raw": "ignored"}],
            "top_losers": [],
            "top_turnover": [],
            "top_traded_shares": [],
            "top_transactions": [],
            "raw_upstream": "ignored",
        }

        response = self.client.get("/api/v1/market/overview/")

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("raw_upstream", response.data)
        self.assertNotIn("internal", response.data["market_summary"])
        self.assertNotIn("raw", response.data["indices"][0])

    def test_company_list(self):
        self.sharehub.get_home_page_data.return_value = {
            "companies": [
                {
                    "symbol": "AAA",
                    "name": "A Company",
                    "sector": "Banking",
                    "ltp": 100,
                    "change": 2,
                    "change_percent": 2,
                    "raw": "ignored",
                }
            ]
        }

        response = self.client.get("/api/v1/market/companies/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]["symbol"], "AAA")
        self.assertNotIn("raw", response.data[0])

    def test_company_detail(self):
        self.sharehub.get_home_page_data.return_value = {
            "companies": [
                {
                    "symbol": "AAA",
                    "name": "A Company",
                    "open": 95,
                    "high": 105,
                    "low": 90,
                    "ltp": 100,
                    "change": 2,
                    "change_percent": 2,
                    "volume": 1000,
                    "raw": "ignored",
                }
            ]
        }

        response = self.client.get("/api/v1/market/companies/aaa/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["symbol"], "AAA")
        self.assertEqual(response.data["volume"], 1000)
        self.assertNotIn("raw", response.data)

    def test_company_candles(self):
        self.sharehub.get_company_candles.return_value = [
            {
                "date": "2026-09-18",
                "open": 95,
                "high": 105,
                "low": 90,
                "close": 100,
                "volume": 10,
                "raw": "ignored",
            }
        ]

        response = self.client.get("/api/v1/market/companies/gbime/candles/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]["close"], "100.0000")
        self.assertNotIn("raw", response.data[0])
        self.sharehub.get_company_candles.assert_called_once_with("gbime")

    def test_index_candles(self):
        self.sharehub.get_index_candles.return_value = [
            {
                "date": "2026-09-18",
                "open": 2000,
                "high": 2050,
                "low": 1990,
                "close": 2040,
            }
        ]

        response = self.client.get("/api/v1/market/indices/NEPSE/candles/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]["date"], "2026-09-18")

    def test_gainers_losers(self):
        self.sharehub.get_top_gainers_losers.return_value = {
            "gainers": [{"symbol": "AAA", "change_percent": 5, "raw": "ignored"}],
            "losers": [{"symbol": "BBB", "change_percent": -5}],
        }

        response = self.client.get("/api/v1/market/gainers-losers/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["gainers"][0]["symbol"], "AAA")
        self.assertNotIn("raw", response.data["gainers"][0])

    def test_change_summary(self):
        self.sharehub.get_change_summary.return_value = [
            {
                "name": "3 Days",
                "change": 10,
                "change_percent": 2.5,
                "raw": "ignored",
            }
        ]

        response = self.client.get("/api/v1/market/change-summary/MATRI/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]["name"], "3 Days")
        self.assertNotIn("raw", response.data[0])

    def test_invalid_symbol_returns_400(self):
        response = self.client.get("/api/v1/market/companies/A_B/")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "Invalid market symbol.")

    def test_sharehub_failure_returns_consistent_503(self):
        self.sharehub.get_market_status.side_effect = ShareHubError()

        response = self.client.get("/api/v1/market/status/")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.data["detail"], "Market data is temporarily unavailable."
        )
