"""
Comprehensive automated test suite for Translation subsystem (Step 31).
"""
import pytest
from translation.core.cache import TranslationCache
from translation.core.detector import LocaleDetector
from translation.core.i18n import LocalizationManager
from translation.core.middleware import AutoTranslateMiddleware
from translation.core.models import (
    LanguageCode,
    ScriptType,
    TranslationRequest,
)
from translation.engines.gateway_engine import GatewayTranslationEngine
from translation.engines.mock_engine import MockOfflineTranslationEngine


def test_locale_detector_scripts():
    detector = LocaleDetector()

    # Korean
    res_ko = detector.detect("안녕하세요 세계")
    assert res_ko.language == "ko"
    assert res_ko.script == ScriptType.HANGUL

    # Chinese
    res_zh = detector.detect("你好世界，今天天气很好")
    assert res_zh.language == "zh"
    assert res_zh.script == ScriptType.HANZI

    # Japanese
    res_ja = detector.detect("こんにちは世界、ありがとう")
    assert res_ja.language == "ja"
    assert res_ja.script == ScriptType.HANZI

    # Hindi
    res_hi = detector.detect("नमस्ते दुनिया")
    assert res_hi.language == "hi"
    assert res_hi.script == ScriptType.DEVANAGARI

    # Arabic
    res_ar = detector.detect("مرحبا بالعالم")
    assert res_ar.language == "ar"
    assert res_ar.script == ScriptType.ARABIC

    # Russian
    res_ru = detector.detect("Здравствуйте мир")
    assert res_ru.language == "ru"
    assert res_ru.script == ScriptType.CYRILLIC

    # Spanish Latin heuristic
    res_es = detector.detect("Hola amigo muchas gracias por favor")
    assert res_es.language == "es"
    assert res_es.script == ScriptType.LATIN

    # French Latin heuristic
    res_fr = detector.detect("Bonjour tout le monde merci beaucoup")
    assert res_fr.language == "fr"
    assert res_fr.script == ScriptType.LATIN

    # German Latin heuristic
    res_de = detector.detect("Guten morgen hallo danke bitte")
    assert res_de.language == "de"
    assert res_de.script == ScriptType.LATIN

    # English Latin default
    res_en = detector.detect("The quick brown fox jumps over the lazy dog")
    assert res_en.language == "en"
    assert res_en.script == ScriptType.LATIN


@pytest.mark.asyncio
async def test_mock_offline_engine():
    engine = MockOfflineTranslationEngine()

    # English -> Spanish
    es_trans = await engine.translate("Hello", "en", "es")
    assert es_trans == "Hola"

    # Spanish -> English
    en_trans = await engine.translate("Hola", "es", "en")
    assert en_trans == "Hello"

    # English -> Chinese
    zh_trans = await engine.translate("Thank you", "en", "zh")
    assert zh_trans == "谢谢"

    # English -> Hindi
    hi_trans = await engine.translate("Hello", "en", "hi")
    assert hi_trans == "नमस्ते"

    # Arbitrary phrase
    custom_trans = await engine.translate("Quantum computing system", "en", "fr")
    assert custom_trans == "[FR] Quantum computing system"


def test_translation_cache_lru_and_sha256():
    cache = TranslationCache(max_entries=3)

    # Initial state
    assert cache.size() == 0
    assert cache.hits == 0
    assert cache.misses == 0

    # Miss
    val = cache.get("en", "es", "Hello")
    assert val is None
    assert cache.misses == 1

    # Set and Hit
    cache.set("en", "es", "Hello", "Hola", "mock_offline")
    assert cache.size() == 1

    hit_val = cache.get("en", "es", "Hello")
    assert hit_val is not None
    assert hit_val[0] == "Hola"
    assert hit_val[1] == "mock_offline"
    assert cache.hits == 1

    # Fill and exceed capacity
    cache.set("en", "fr", "Hello", "Bonjour", "mock_offline")
    cache.set("en", "de", "Hello", "Hallo", "mock_offline")
    assert cache.size() == 3

    cache.set("en", "zh", "Hello", "你好", "mock_offline")
    assert cache.size() == 3  # Evicted oldest entry ("en", "es", "Hello")

    # Oldest was evicted
    assert cache.get("en", "es", "Hello") is None


def test_localization_manager():
    i18n = LocalizationManager(default_locale="en")

    # English default
    assert i18n.t("status_idle", "en") == "Idle"

    # Spanish
    assert i18n.t("status_idle", "es") == "Inactivo"

    # French with formatting kwargs
    task_fr = i18n.t("task_completed", "fr", task_name="BackupDatabase")
    assert "BackupDatabase" in task_fr
    assert "terminée avec succès" in task_fr

    # German
    assert i18n.t("error_network", "de") == "Netzwerkverbindungsfehler."

    # Chinese
    assert i18n.t("status_processing", "zh") == "正在处理请求..."

    # Fallback to English when key is missing in target locale
    i18n.register_bundle("it", {"custom_key": "Ciao"})
    assert i18n.t("status_idle", "it") == "Idle"
    assert i18n.t("custom_key", "it") == "Ciao"


@pytest.mark.asyncio
async def test_auto_translate_middleware_inbound_outbound():
    middleware = AutoTranslateMiddleware()

    # 1. User says "Hola" (auto-detected as Spanish), translate to English
    inbound_res = await middleware.translate_inbound("Hola", agent_lang="en")
    assert inbound_res.detected_source_lang == "es"
    assert inbound_res.target_lang == "en"
    assert inbound_res.translated_text == "Hello"
    assert inbound_res.cached is False

    # 2. Agent responds in English "Good morning", translate to Spanish for the user
    outbound_res = await middleware.translate_outbound("Good morning", user_lang="es", agent_lang="en")
    assert outbound_res.target_lang == "es"
    assert outbound_res.translated_text == "Buenos días"
    assert outbound_res.cached is False


@pytest.mark.asyncio
async def test_auto_translate_middleware_caching():
    middleware = AutoTranslateMiddleware()

    req = TranslationRequest(text="Thank you", source_lang="en", target_lang="es")

    # First call - not cached
    res1 = await middleware.execute(req)
    assert res1.translated_text == "Gracias"
    assert res1.cached is False

    # Second call - cached
    res2 = await middleware.execute(req)
    assert res2.translated_text == "Gracias"
    assert res2.cached is True


@pytest.mark.asyncio
async def test_auto_translate_middleware_same_language_noop():
    middleware = AutoTranslateMiddleware()

    req = TranslationRequest(text="Already in English", source_lang="en", target_lang="en")
    res = await middleware.execute(req)
    assert res.translated_text == "Already in English"
    assert res.engine == "noop"
    assert res.cached is False


@pytest.mark.asyncio
async def test_gateway_translation_engine_fallback():
    gateway_engine = GatewayTranslationEngine()
    assert gateway_engine.name() == "model_gateway"

    translated = await gateway_engine.translate("Hello", "en", "de")
    assert translated == "Hallo"


def test_unsupported_locale_language_fallback():
    """Verify fallback when an unsupported locale is requested."""
    i18n = LocalizationManager(default_locale="en")

    # 1. Totally unknown/unsupported locale code falls back cleanly to 'en'
    res_unknown = i18n.t("status_idle", locale="xx-klingon")
    assert res_unknown == "Idle"

    # 2. Key with parameters on unsupported locale
    res_task = i18n.t("task_completed", locale="unknown_locale", task_name="IndexFiles")
    assert res_task == "Task 'IndexFiles' completed successfully."

    # 3. Non-existent key in both target and default bundles returns the raw key without exception
    res_nonexistent = i18n.t("completely_missing_key", locale="unsupported")
    assert res_nonexistent == "completely_missing_key"

    # 4. Partial locale bundle missing a key falls back to default locale
    i18n.register_bundle("pt", {"status_idle": "Inativo"})
    assert i18n.t("status_idle", locale="pt") == "Inativo"
    # missing key in pt falls back to en
    assert i18n.t("error_network", locale="pt") == "Network connection error."


def test_offline_translation_engine_adapter():
    """Done when: translate('Bonjour', target='en') returns 'Hello'."""
    from translation.core.engine import OfflineTranslationEngine, translate

    # 1. Verification Gate: translate("Bonjour", target="en") returns "Hello"
    result = translate("Bonjour", target="en")
    assert result == "Hello"

    # 2. Automatic language detection and translation for other languages
    engine = OfflineTranslationEngine()
    assert engine.translate("Bonjour", target="en") == "Hello"
    assert engine.translate("Hola", target="en") == "Hello"
    assert engine.translate("Danke", target="en") == "Thank you"
    assert engine.translate("Hello", target="es") == "Hola"
    assert engine.translate("Hello", target="fr") == "Bonjour"

    # 3. Cache verification
    cached_entry = engine.cache.get("fr", "en", "Bonjour")
    assert cached_entry is not None
    assert cached_entry[0] == "Hello"

    # 4. Same language no-op
    assert engine.translate("Pheonix System", target="en", source="en") == "Pheonix System"
