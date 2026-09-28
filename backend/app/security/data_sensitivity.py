"""Data sensitivity classification model for sovereign workbench."""

from enum import Enum
from typing import Union


class DataSensitivity(str, Enum):
    """Data sensitivity tiers controlling policy and risk exposure."""
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    CONFIDENTIAL = "CONFIDENTIAL"
    RESTRICTED = "RESTRICTED"


def parse_data_sensitivity(value: Union[str, DataSensitivity, None]) -> DataSensitivity:
    """Safely parse sensitivity with fail-closed behavior to INTERNAL if unspecified."""
    if value is None:
        return DataSensitivity.INTERNAL
    if isinstance(value, DataSensitivity):
        return value
    val_upper = str(value).strip().upper()
    try:
        return DataSensitivity(val_upper)
    except ValueError:
        # Fail-closed default: if unknown string supplied, treat as RESTRICTED
        return DataSensitivity.RESTRICTED
