# Copyright (c) 2023-2025 Arista Networks, Inc.
# Use of this source code is governed by the Apache License 2.0
# that can be found in the LICENSE file.
from __future__ import annotations

from typing import Any

from pyavd._anta.models import EthernetInterface, MinimalStructuredConfig
from pyavd._utils import get


def get_fabric_data(structured_configs: dict[str, dict[str, Any]]) -> dict[str, MinimalStructuredConfig]:
    """
    Get minimal fabric-wide data required to generate tests.

    The returned dictionary is intended to be passed to `pyavd.get_device_test_catalog` for generating ANTA catalogs.

    Args:
        structured_configs: A dictionary keyed by hostname containing structured configurations for all devices.
            Each structured config should be converted and validated according to AVD `eos_cli_config_gen`
            schema first using `pyavd.validate_structured_config`.

    Returns:
        A dictionary keyed by hostname containing a `MinimalStructuredConfig` dataclass instance for each device.
    """
    minimal_structured_configs: dict[str, MinimalStructuredConfig] = {}

    for device, structured_config in structured_configs.items():
        # Parse the Ethernet interfaces
        minimal_ethernet_interfaces = [
            EthernetInterface(
                name=intf["name"], ip_address=intf_ip, shutdown=get(intf, "shutdown", get(structured_config, "interface_defaults.ethernet.shutdown", False))
            )
            for intf in get(structured_config, "ethernet_interfaces", default=[])
            if (intf_ip := get(intf, "ip_address")) and get(intf, "switchport.enabled") is False
        ]

        # Create the minimal structured configuration
        minimal_structured_configs[device] = MinimalStructuredConfig(
            hostname=structured_config["hostname"],
            is_deployed=get(structured_config, "metadata.is_deployed", default=False),
            dns_domain=get(structured_config, "dns_domain"),
            ethernet_interfaces=minimal_ethernet_interfaces,
        )
    return minimal_structured_configs
