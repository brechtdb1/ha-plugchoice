"""Sensors of the Plugchoice charger (read-only)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import PlugchoiceConfigEntry
from .const import OCPP_STATUSES, PLUGGED_STATUSES
from .coordinator import PlugchoiceData
from .entity import PlugchoiceEntity


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _ts(value: Any) -> datetime | None:
    return dt_util.parse_datetime(value) if isinstance(value, str) else None


def _phase_current(phase: str) -> Callable[[PlugchoiceData], float | None]:
    """Current per phase. power-usage keeps the last measurement, also when charging
    has stopped; without a car on the cable we therefore show 0 A."""

    def value(d: PlugchoiceData) -> float | None:
        if d.status not in PLUGGED_STATUSES:
            return 0.0
        return _float(d.power_usage.get(phase))

    return value


def _power(d: PlugchoiceData) -> float | None:
    if d.status not in PLUGGED_STATUSES:
        return 0.0
    return _float(d.power_usage.get("kW"))


def _session_energy(d: PlugchoiceData) -> float | None:
    """Energy of the running or last session in kWh."""
    tx = d.last_transaction
    if not tx:
        return None
    # Plugchoice also updates total_kwh during a running session.
    if (total := _float(tx.get("total_kwh"))) is not None:
        return total
    register = d.meter_values.get("Energy.Active.Import.Register")
    start = _float(tx.get("meter_start"))
    if register is not None and start is not None:
        return round(register - start / 1000, 3)
    return None


def _meter(key: str) -> Callable[[PlugchoiceData], float | None]:
    """Value from the latest MeterValues, only while a session is running.
    Outside a session the charger only sends the energy meter (every 15 minutes)."""

    def value(d: PlugchoiceData) -> float | None:
        if not d.transaction_active:
            return None
        return d.meter_values.get(key)

    return value


@dataclass(frozen=True, kw_only=True)
class PlugchoiceSensorDescription(SensorEntityDescription):
    value_fn: Callable[[PlugchoiceData], Any]
    attrs_fn: Callable[[PlugchoiceData], dict[str, Any]] | None = None


# key = part of the unique_id (kept from the first version), translation_key = name.
SENSORS: tuple[PlugchoiceSensorDescription, ...] = (
    PlugchoiceSensorDescription(
        key="status",
        translation_key="status",
        icon="mdi:ev-station",
        device_class=SensorDeviceClass.ENUM,
        options=OCPP_STATUSES,
        value_fn=lambda d: d.status if d.status in OCPP_STATUSES else None,
        attrs_fn=lambda d: {"error": d.connector.get("error"), "error_info": d.connector.get("error_info")},
    ),
    PlugchoiceSensorDescription(
        key="vermogen",
        translation_key="power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        suggested_display_precision=2,
        value_fn=_power,
        attrs_fn=lambda d: {"updated_at_ms": d.power_usage.get("kw_updated_at")},
    ),
    *(
        PlugchoiceSensorDescription(
            key=f"stroom_{p.lower()}",
            translation_key=f"current_{p.lower()}",
            device_class=SensorDeviceClass.CURRENT,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
            suggested_display_precision=1,
            value_fn=_phase_current(p),
            attrs_fn=lambda d: {"measured_at": d.power_usage.get("timestamp")},
        )
        for p in ("L1", "L2", "L3")
    ),
    PlugchoiceSensorDescription(
        key="aangeboden_stroom",
        translation_key="current_offered",
        icon="mdi:current-ac",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        # Current.Offered = the limit the charger really applies, whoever set it
        # (an OCPP backend, Plugchoice or the API).
        value_fn=_meter("Current.Offered"),
    ),
    *(
        PlugchoiceSensorDescription(
            key=f"spanning_{p.lower()}",
            translation_key=f"voltage_{p.lower()}",
            device_class=SensorDeviceClass.VOLTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfElectricPotential.VOLT,
            suggested_display_precision=0,
            entity_category=EntityCategory.DIAGNOSTIC,
            value_fn=_meter(f"Voltage.{p}-N"),
        )
        for p in ("L1", "L2", "L3")
    ),
    PlugchoiceSensorDescription(
        key="temperatuur",
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_meter("Temperature"),
    ),
    PlugchoiceSensorDescription(
        key="energie_totaal",
        translation_key="energy_total",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
        value_fn=lambda d: d.meter_values.get("Energy.Active.Import.Register"),
        attrs_fn=lambda d: {"measured_at": d.meter_timestamp},
    ),
    PlugchoiceSensorDescription(
        key="sessie_energie",
        translation_key="session_energy",
        icon="mdi:battery-charging",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
        value_fn=_session_energy,
        attrs_fn=lambda d: {
            "active": d.transaction_active,
            "stop_reason": (d.last_transaction or {}).get("stop_reason"),
        },
    ),
    PlugchoiceSensorDescription(
        key="sessie_start",
        translation_key="session_started",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda d: _ts((d.last_transaction or {}).get("started_at")),
    ),
    PlugchoiceSensorDescription(
        key="sessie_einde",
        translation_key="session_stopped",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda d: None if d.transaction_active else _ts((d.last_transaction or {}).get("stopped_at")),
    ),
    PlugchoiceSensorDescription(
        key="laadlimiet",
        translation_key="charge_limit",
        icon="mdi:speedometer",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        value_fn=lambda d: _float(d.connector.get("current_limit")),
        attrs_fn=lambda d: {"managed_by": d.connector.get("current_limit_managed_by")},
    ),
    PlugchoiceSensorDescription(
        key="max_stroom",
        translation_key="max_current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: _float(d.connector.get("max_amperage") or d.charger.get("max_current")),
        attrs_fn=lambda d: {"min_current": d.connector.get("min_current"), "power_type": d.connector.get("power_type")},
    ),
    PlugchoiceSensorDescription(
        key="laatste_heartbeat",
        translation_key="last_heartbeat",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: _ts(d.charger.get("last_heartbeat_at")),
    ),
    PlugchoiceSensorDescription(
        key="firmware",
        translation_key="firmware",
        icon="mdi:chip",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.charger.get("parsed_firmware_version"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: PlugchoiceConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data.coordinator
    async_add_entities(PlugchoiceSensor(coordinator, desc) for desc in SENSORS)


class PlugchoiceSensor(PlugchoiceEntity, SensorEntity):
    entity_description: PlugchoiceSensorDescription

    def __init__(self, coordinator, description: PlugchoiceSensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        fn = self.entity_description.attrs_fn
        return fn(self.coordinator.data) if fn else None
