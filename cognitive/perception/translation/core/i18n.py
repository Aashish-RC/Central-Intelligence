"""
Localization (i18n) Manager for system UI alerts, notices, and message bundles.
"""
from __future__ import annotations

from typing import Any, Dict, Optional


DEFAULT_BUNDLES: Dict[str, Dict[str, str]] = {
    "en": {
        "status_idle": "Idle",
        "status_processing": "Processing request...",
        "task_completed": "Task '{task_name}' completed successfully.",
        "permission_denied": "Permission denied for operation '{operation}'.",
        "error_network": "Network connection error.",
    },
    "es": {
        "status_idle": "Inactivo",
        "status_processing": "Procesando solicitud...",
        "task_completed": "Tarea '{task_name}' completada con éxito.",
        "permission_denied": "Permiso denegado para la operación '{operation}'.",
        "error_network": "Error de conexión de red.",
    },
    "fr": {
        "status_idle": "Inactif",
        "status_processing": "Traitement de la demande en cours...",
        "task_completed": "Tâche '{task_name}' terminée avec succès.",
        "permission_denied": "Permission refusée pour l'opération '{operation}'.",
        "error_network": "Erreur de connexion réseau.",
    },
    "de": {
        "status_idle": "Inaktiv",
        "status_processing": "Anfrage wird bearbeitet...",
        "task_completed": "Aufgabe '{task_name}' erfolgreich abgeschlossen.",
        "permission_denied": "Berechtigung für Vorgang '{operation}' verweigert.",
        "error_network": "Netzwerkverbindungsfehler.",
    },
    "zh": {
        "status_idle": "空闲",
        "status_processing": "正在处理请求...",
        "task_completed": "任务 '{task_name}' 已成功完成。",
        "permission_denied": "操作 '{operation}' 权限被拒绝。",
        "error_network": "网络连接错误。",
    },
}


class LocalizationManager:
    """Provides dictionary-based localized string resolution with fallback."""

    def __init__(self, default_locale: str = "en"):
        self.default_locale = default_locale
        self._bundles: Dict[str, Dict[str, str]] = {k: dict(v) for k, v in DEFAULT_BUNDLES.items()}

    def register_bundle(self, locale: str, strings: Dict[str, str]) -> None:
        norm = locale.lower().strip()
        if norm not in self._bundles:
            self._bundles[norm] = {}
        self._bundles[norm].update(strings)

    def t(self, key: str, locale: Optional[str] = None, **kwargs: Any) -> str:
        target_locale = (locale or self.default_locale).lower().strip()

        # Try target locale
        bundle = self._bundles.get(target_locale)
        template = bundle.get(key) if bundle else None

        # Fallback to default locale
        if template is None:
            fallback_bundle = self._bundles.get(self.default_locale, {})
            template = fallback_bundle.get(key, key)

        if kwargs:
            try:
                return template.format(**kwargs)
            except Exception:
                return template

        return template
