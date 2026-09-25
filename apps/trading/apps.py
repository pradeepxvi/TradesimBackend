from django.apps import AppConfig


class TradingConfig(AppConfig):
    name = "apps.trading"

    def ready(self):
        from . import signals  # noqa: F401
