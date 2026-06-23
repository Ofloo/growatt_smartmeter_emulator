"""Config flow for SmartMeter Emulator."""
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_SLAVE,
)
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import DOMAIN

STEP_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default="0.0.0.0"): str,
        vol.Required(CONF_PORT, default=502): int,
        vol.Required(CONF_SLAVE, default=1): int,
        vol.Required("power_sensor"): EntitySelector(
            EntitySelectorConfig(domain="sensor", device_class="power")
        ),
        vol.Optional("voltage_sensor"): EntitySelector(
            EntitySelectorConfig(domain="sensor", device_class="voltage")
        ),
        vol.Optional("current_sensor"): EntitySelector(
            EntitySelectorConfig(domain="sensor", device_class="current")
        ),
        vol.Optional("frequency", default=50): SelectSelector(
            SelectSelectorConfig(
                options=["50", "60"],
                mode=SelectSelectorMode.DROPDOWN,
                translation_key="frequency",
            )
        ),
        vol.Optional("debug_logging", default=False): bool,
    }
)


async def validate_input(hass: HomeAssistant, data: dict) -> dict[str, str]:
    """Validate the user input allows us to connect."""
    errors = {}

    if not data[CONF_HOST]:
        errors[CONF_HOST] = "invalid_host"

    if not (1 <= data[CONF_PORT] <= 65535):
        errors[CONF_PORT] = "invalid_port"

    if not (1 <= data[CONF_SLAVE] <= 255):
        errors[CONF_SLAVE] = "invalid_slave"

    if not data.get("power_sensor"):
        errors["power_sensor"] = "required_sensor"

    if "debug_logging" not in data:
        data["debug_logging"] = False

    if errors:
        raise InvalidInput(errors=errors)

    return {"title": "Growatt Meter Emulator"}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SmartMeter Emulator."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> dict[str, str]:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_DATA_SCHEMA
            )

        errors = {}

        try:
            info = await validate_input(self.hass, user_input)
        except InvalidInput as err:
            if err.errors:
                errors = err.errors
            else:
                errors["base"] = "unknown"
        except Exception:
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_DATA_SCHEMA, errors=errors
        )


class InvalidInput(HomeAssistantError):
    """Error to indicate we cannot connect."""

    def __init__(self, errors: dict[str, str]) -> None:
        """Initialize."""
        super().__init__("Invalid input")
        self.errors = errors
