"""Base entity for the MicroAir_EasyTouch integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MicroAirCoordinatorHub


class MicroAirEntity(CoordinatorEntity[MicroAirCoordinatorHub]):
    """Representation of a MicroAirTouch entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: MicroAirCoordinatorHub) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            name=coordinator.name,
            manufacturer="MicroAir",
            model="MicroAir Easy Touch OEM",
        )
