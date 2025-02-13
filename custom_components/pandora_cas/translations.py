"""Load web translations"""

__all__ = (
    "get_config_entry_language",
    "get_web_translations_value",
    "async_load_web_translations",
)

import logging
from datetime import datetime
from json import JSONDecodeError
from time import time
from typing import Final

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LANGUAGE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store

from custom_components.pandora_cas.const import (
    DEFAULT_LANGUAGE,
    DATA_WEB_TRANSLATIONS,
    DATA_WEB_TRANSLATIONS_STORE,
)

_LOGGER: Final = logging.getLogger(__name__)


def get_config_entry_language(entry: ConfigEntry) -> str:
    """Get web translations language from configuration entry options."""
    if entry.options is None:
        return DEFAULT_LANGUAGE
    return entry.options.get(CONF_LANGUAGE) or DEFAULT_LANGUAGE


def get_web_translations_value(
    hass: HomeAssistant, language: str, key: str
) -> str | None:
    """Retrieve value from web translations language dictionary."""
    try:
        web_translations = hass.data[DATA_WEB_TRANSLATIONS]
    except KeyError:
        return None

    try:
        return web_translations[language][key]
    except KeyError:
        if language != DEFAULT_LANGUAGE:
            return get_web_translations_value(hass, DEFAULT_LANGUAGE, key)
        return "!!!" + key + "!!!"


async def async_load_web_translations(
    hass: HomeAssistant,
    language: str,
    session: aiohttp.ClientSession | bool | None = None,
    ignore_recency: bool = False,
) -> dict[str, str]:
    """Load web translations."""
    if (language := language.lower()) == "last_update":
        raise ValueError("how?")

    try:
        # Retrieve initialized store
        store = hass.data[DATA_WEB_TRANSLATIONS_STORE]
    except KeyError:
        hass.data[DATA_WEB_TRANSLATIONS_STORE] = store = Store(
            hass,
            1,
            DATA_WEB_TRANSLATIONS,
        )

    try:
        # Retrieve cached data
        saved_data = hass.data[DATA_WEB_TRANSLATIONS]
    except KeyError:
        # Retrieve stored data
        saved_data = await store.async_load()

        # Provide fallback for corrupt or empty data
        if not isinstance(saved_data, dict):
            saved_data = {}

        # Cache loaded data
        hass.data[DATA_WEB_TRANSLATIONS] = saved_data

    language_data = None
    if saved_data:
        try:
            last_update = float(saved_data["last_update"][language])
        except (KeyError, ValueError, TypeError):
            _LOGGER.info(
                f"Data for language {language} is missing "
                f"valid timestamp information."
            )
        else:
            if ignore_recency:
                _LOGGER.info(
                    f"Translation data for language {language} will be downloaded immediately."
                )
            elif (time() - last_update) > (7 * 24 * 60 * 60):
                _LOGGER.info(
                    f"Last data retrieval for language {language} "
                    f"occurred on {datetime.fromtimestamp(last_update).isoformat()}, "
                    f"assuming data is stale."
                )
            elif not isinstance((language_data := saved_data.get(language)), dict):
                _LOGGER.warning(
                    f"Data for language {language} is missing, "
                    f"assuming storage is corrupt."
                )
            else:
                _LOGGER.info(
                    f"Data for language {language} is recent, no updates required."
                )
                return saved_data[language]
    else:
        _LOGGER.info("Translation data store initialization required.")

    _LOGGER.info(f"Will attempt to download translations for language: {language}")

    if session is None:
        session = async_get_clientsession(hass)
    elif isinstance(session, bool):
        session = async_get_clientsession(hass, verify_ssl=session)
    elif not isinstance(session, aiohttp.ClientSession):
        raise HomeAssistantError("Invalid session parameter")

    try:
        async with session.get(
            f"https://p-on.ru/local/web/{language}.json"
        ) as response:
            new_data = await response.json()
    except (aiohttp.ClientError, JSONDecodeError):
        if isinstance((language_data := saved_data.get(language)), dict):
            _LOGGER.warning(
                f"Could not download translations for language "
                f"{language}, will fall back to stale data."
            )
            return language_data
        elif language == DEFAULT_LANGUAGE:
            _LOGGER.error(f"Failed loading fallback language")
            raise
        new_data = None

    # Use fallback web translations because decoded data is bad
    if not isinstance(new_data, dict):
        _LOGGER.error(
            f"Could not decode translations "
            f"for language {language}, falling "
            f"back to {DEFAULT_LANGUAGE}",
        )
        return await async_load_web_translations(hass, DEFAULT_LANGUAGE)

    if not isinstance(language_data, dict):
        saved_data[language] = language_data = {}

    # Fix-ups (QoL) for data
    for key, value in new_data.items():
        if value is None or not (value := str(value).strip()):
            continue
        if key.startswith("event-name-"):
            # Uppercase only first character
            value = value[0].upper() + value[1:]
        elif key.startswith("event-subname-"):
            # Lowercase only first character
            value = value[0].lower() + value[1:]
        language_data[key] = value

    saved_data.setdefault("last_update", {})[language] = time()

    await store.async_save(saved_data)

    _LOGGER.info(f"Data for language {language} updated successfully.")
    return language_data
