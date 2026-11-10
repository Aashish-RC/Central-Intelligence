"""Localization & Internationalization Manager (L18 Interaction - Task 18.40).

Supports multi-language string lookup, currency/number formatting,
and automatic Right-to-Left (RTL) text direction detection for languages such as Arabic, Hebrew, and Persian.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Known Right-To-Left (RTL) language prefixes
RTL_LANGUAGES = {"ar", "he", "fa", "ur"}


@dataclass
class LocaleProfile:
    """User language and regional formatting preferences."""
    locale_code: str = "en-US"
    language_code: str = "en"
    is_rtl: bool = False
    currency: str = "USD"
    date_format: str = "YYYY-MM-DD"


class LocalizationManager:
    """Manages internationalization, locale switching, and RTL text layout."""

    def __init__(self, initial_locale: str = "en-US") -> None:
        self.locale = self._build_profile(initial_locale)
        self._translations: Dict[str, Dict[str, str]] = {
            "en": {
                "welcome": "Welcome to Central Intelligence",
                "settings": "Settings",
                "save": "Save Changes",
            },
            "ar": {
                "welcome": "مرحبًا بك في الاستخبارات المركزية",
                "settings": "الإعدادات",
                "save": "حفظ التغييرات",
            },
            "es": {
                "welcome": "Bienvenido a Central Intelligence",
                "settings": "Ajustes",
                "save": "Guardar cambios",
            },
        }

    def _build_profile(self, locale_code: str) -> LocaleProfile:
        lang = locale_code.split("-")[0].lower()
        is_rtl = lang in RTL_LANGUAGES
        currency = "SAR" if lang == "ar" else ("EUR" if lang == "es" else "USD")
        return LocaleProfile(
            locale_code=locale_code,
            language_code=lang,
            is_rtl=is_rtl,
            currency=currency,
        )

    def set_locale(self, locale_code: str) -> LocaleProfile:
        """Change current locale and update RTL orientation automatically."""
        self.locale = self._build_profile(locale_code)
        logger.info("Updated locale to %s (is_rtl=%s)", locale_code, self.locale.is_rtl)
        return self.locale

    def translate(self, key: str, default: Optional[str] = None) -> str:
        """Fetch localized string for active language."""
        lang_dict = self._translations.get(self.locale.language_code, self._translations["en"])
        return lang_dict.get(key, default or key)
