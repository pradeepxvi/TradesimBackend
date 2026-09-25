import re
from urllib.parse import urljoin

import requests
from django.conf import settings


class ShareHubError(Exception):
    """Raised when ShareHub cannot provide a usable response."""


class InvalidSymbolError(ValueError):
    """Raised when a stock or index symbol is unsafe or invalid."""


class ShareHubClient:
    """Small client for the ShareHub Nepal market-data endpoints."""

    DEFAULT_TIMEOUT = 10
    SYMBOL_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9.-]*$")

    def __init__(self, base_url=None, timeout=DEFAULT_TIMEOUT, session=None):
        self.base_url = (base_url or settings.SHAREHUB_BASE_URL).rstrip("/") + "/"
        self.timeout = timeout
        self.session = session or requests.Session()

    def get_market_status(self):
        payload = self._get("/live/api/v1/nepselive/market-status")
        data = self._as_mapping(payload)
        return self._pick_fields(
            data,
            {
                "status": (
                    "status",
                    "marketStatus",
                    "market_status",
                    "isOpen",
                ),
                "is_open": ("isOpen", "is_open", "marketOpen"),
                "message": ("message", "description"),
                "updated_at": (
                    "updatedAt",
                    "updated_at",
                    "lastUpdatedDateTime",
                    "time",
                    "asOf",
                ),
            },
        )

    def get_home_page_data(self):
        payload = self._get("/live/api/v2/nepselive/home-page-data")
        data = self._as_mapping(payload)
        result = {}
        aliases = {
            "market_status": ("marketStatus", "market_status", "status"),
            "market_summary": ("marketSummary", "market_summary", "summary"),
            "stock_summary": ("stockSummary", "stock_summary"),
            "indices": ("indices", "indexData", "index_data"),
            "top_gainers": ("topGainers", "top_gainers", "gainers"),
            "top_losers": ("topLosers", "top_losers", "losers"),
            "top_turnover": ("topTurnover", "top_turnover"),
            "top_traded_shares": ("topTradedShares", "top_traded_shares"),
            "top_transactions": ("topTransactions", "top_transactions"),
            "companies": (
                "companies",
                "companyList",
                "company_list",
                "stockList",
                "securityList",
                "liveCompanyData",
            ),
        }
        for name, keys in aliases.items():
            value = self._first_value(data, keys)
            if value is None:
                continue
            if name in {
                "top_gainers",
                "top_losers",
                "indices",
                "top_turnover",
                "top_traded_shares",
                "top_transactions",
                "companies",
            }:
                value = self._normalize_records(value)
            elif name in {"market_summary", "stock_summary"}:
                value = self._normalize_summary(value)
            elif name == "market_status" and isinstance(value, dict):
                value = self._normalize_market_status(value)
            elif isinstance(value, dict):
                value = self._normalize_quote(value)
            result[name] = value
        return result

    def get_company_candles(self, symbol):
        symbol = self._validate_symbol(symbol)
        payload = self._get(f"/live/api/v1/daily-graph/company/candle/{symbol}")
        return self._normalize_candles(payload)

    def get_index_candles(self, symbol):
        symbol = self._validate_symbol(symbol)
        payload = self._get(f"/live/api/v1/daily-graph/index/candle/{symbol}")
        return self._normalize_candles(payload)

    def get_top_gainers_losers(self):
        payload = self._get("/data/api/v1/price-history/top-gainers-losers")
        data = self._as_mapping(payload)
        gainers = self._first_value(data, ("gainers", "topGainers", "top_gainers"))
        losers = self._first_value(data, ("losers", "topLosers", "top_losers"))
        if gainers is None and losers is None:
            records = self._normalize_records(data.get("content", []))
            gainers = [
                record
                for record in records
                if self._as_number(record.get("change_percent")) > 0
            ]
            losers = [
                record
                for record in records
                if self._as_number(record.get("change_percent")) < 0
            ]
            if not losers:
                try:
                    homepage = self.get_home_page_data()
                    losers = homepage.get("top_losers", [])
                except ShareHubError:
                    losers = []
        return {
            "gainers": self._normalize_records(gainers),
            "losers": self._normalize_records(losers),
        }

    def get_change_summary(self, symbol):
        symbol = self._validate_symbol(symbol)
        payload = self._get(f"/data/api/v1/price-history/change-summary/{symbol}")
        return self._normalize_change_summary(payload)

    def _get(self, path):
        try:
            response = self.session.get(
                urljoin(self.base_url, path.lstrip("/")),
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            raise ShareHubError("ShareHub request failed.") from exc
        except (TypeError, ValueError) as exc:
            raise ShareHubError("ShareHub returned invalid JSON.") from exc

        if not isinstance(payload, (dict, list)):
            raise ShareHubError("ShareHub returned an invalid response.")
        return payload

    @classmethod
    def _validate_symbol(cls, symbol):
        if not isinstance(symbol, str):
            raise InvalidSymbolError("Symbol must be a string.")
        symbol = symbol.strip().upper()
        if not symbol or not cls.SYMBOL_PATTERN.fullmatch(symbol):
            raise InvalidSymbolError("Symbol contains invalid characters.")
        return symbol

    @staticmethod
    def _as_mapping(payload):
        if isinstance(payload, dict):
            data = payload.get("data", payload)
            if isinstance(data, dict):
                return data
        return {}

    @staticmethod
    def _first_value(data, keys):
        for key in keys:
            if key in data and data[key] is not None:
                return data[key]
        return None

    @classmethod
    def _pick_fields(cls, data, fields):
        result = {}
        for normalized_name, source_names in fields.items():
            value = cls._first_value(data, source_names)
            if value is not None:
                result[normalized_name] = value
        return result

    @classmethod
    def _normalize_quote(cls, record):
        if not isinstance(record, dict):
            return {}
        fields = {
            "symbol": ("symbol", "securitySymbol", "stockSymbol"),
            "name": ("name", "securityName", "companyName", "indexName"),
            "sector": ("sector", "sectorName"),
            "open": ("open", "openPrice"),
            "high": ("high", "highPrice"),
            "low": ("low", "lowPrice"),
            "ltp": ("ltp", "lastTradedPrice", "lastPrice", "currentValue"),
            "change": ("change", "changeValue", "pointChange"),
            "change_percent": ("change_percent", "percentageChange", "percentChange"),
            "volume": ("volume", "totalTradeQuantity", "lastTradedVolume"),
            "turnover": ("turnover", "totalTradeValue"),
            "transactions": ("transactions", "totalTransactions"),
            "previous_close": ("previous_close", "previousClose"),
            "updated_at": (
                "updated_at",
                "lastUpdatedDateTime",
                "lastUpdatedTime",
                "updatedAt",
            ),
        }
        return cls._pick_fields(record, fields)

    @staticmethod
    def _as_number(value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0

    @classmethod
    def _normalize_summary(cls, record):
        if isinstance(record, list):
            label_map = {
                "total turnover rs:": "total_turnover",
                "total traded shares": "total_volume",
                "total transactions": "total_transactions",
                "total scrips traded": "total_companies",
            }
            result = {}
            for item in record:
                if not isinstance(item, dict):
                    continue
                label = str(item.get("name", "")).strip().lower()
                field_name = label_map.get(label)
                if field_name and item.get("value") is not None:
                    result[field_name] = item["value"]
            return result
        if not isinstance(record, dict):
            return {}
        return cls._pick_fields(
            record,
            {
                "total_turnover": ("totalTurnover", "totalTradeValue", "turnover"),
                "total_transactions": ("totalTransactions", "transactions"),
                "total_volume": ("totalVolume", "totalTradeQuantity", "volume"),
                "total_companies": ("totalCompanies", "totalSecurities"),
                "total_traded": ("totalTraded", "tradedCompanies"),
                "advances": ("advances", "advanced"),
                "declines": ("declines", "declined"),
                "unchanged": ("unchanged",),
            },
        )

    @classmethod
    def _normalize_market_status(cls, record):
        return cls._pick_fields(
            record,
            {
                "status": ("status", "marketStatus", "state"),
                "is_open": ("isOpen", "is_open", "marketOpen"),
                "updated_at": ("time", "asOf", "updatedAt", "updated_at"),
            },
        )

    @classmethod
    def _normalize_records(cls, value):
        if isinstance(value, dict):
            value = value.get("data", value.get("content", []))
        if not isinstance(value, list):
            return []
        return [
            normalized for item in value if (normalized := cls._normalize_quote(item))
        ]

    @classmethod
    def _normalize_candles(cls, payload):
        if isinstance(payload, dict):
            value = payload.get("data", payload.get("candles", []))
        else:
            value = payload
        if not isinstance(value, list):
            return []

        candles = []
        for item in value:
            if not isinstance(item, dict):
                continue
            candle = cls._pick_fields(
                item,
                {
                    "date": ("date", "time", "timestamp", "tradingDate"),
                    "open": ("open", "openPrice"),
                    "high": ("high", "highPrice"),
                    "low": ("low", "lowPrice"),
                    "close": ("close", "closePrice", "ltp", "lastTradedPrice"),
                    "volume": ("volume", "totalTradeQuantity"),
                },
            )
            if candle:
                candles.append(candle)
        return candles

    @classmethod
    def _normalize_change_summary(cls, payload):
        if isinstance(payload, dict):
            value = payload.get("data", [])
        else:
            value = payload
        if not isinstance(value, list):
            return []
        return [
            normalized
            for item in value
            if isinstance(item, dict)
            and (
                normalized := cls._pick_fields(
                    item,
                    {
                        "name": ("name", "period"),
                        "change": ("change", "changeAdj"),
                        "change_percent": (
                            "changePercent",
                            "change_percent",
                            "changePercentAdj",
                        ),
                        "date": ("date", "asOf", "updatedAt"),
                    },
                )
            )
        ]
