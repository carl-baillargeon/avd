# Copyright (c) 2023-2025 Arista Networks, Inc.
# Use of this source code is governed by the Apache License 2.0
# that can be found in the LICENSE file.
"""Data models used by PyAVD for ANTA."""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from ipaddress import IPv4Address, IPv6Address, ip_interface
from logging import getLogger
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pyavd._eos_cli_config_gen.schema import EosCliConfigGen
    from pyavd.api._anta import MinimalStructuredConfig

LOGGER = getLogger(__name__)


@dataclass(frozen=True)
class BgpNeighbor:
    """Represents a BGP neighbor from the structured configuration."""

    ip_address: IPv4Address | IPv6Address
    vrf: str
    update_source: str | None = None


@dataclass(frozen=True)
class BgpNeighborInterface:
    """Represents a BGP neighbor interface (RFC5549) from the structured configuration."""

    interface: str
    vrf: str


@dataclass
class DeviceTestContext:
    """Stores device test context data for ANTA test generation."""

    hostname: str
    structured_config: EosCliConfigGen
    minimal_structured_configs: dict[str, MinimalStructuredConfig]

    @cached_property
    def is_vtep(self) -> bool:
        """Check if the device is a VTEP."""
        return bool(self.structured_config.vxlan_interface.vxlan1.vxlan._get("source_interface"))

    @cached_property
    def is_wan_router(self) -> bool:
        """Check if the device is a WAN router."""
        return self.is_vtep and "Dps" in self.structured_config.vxlan_interface.vxlan1.vxlan._get("source_interface")

    @cached_property
    def bgp_neighbors(self) -> list[BgpNeighbor]:
        """Generate a list of BGP neighbors for the device."""
        neighbors: list[BgpNeighbor] = []

        # Process default VRF neighbors
        for neighbors_item in self.structured_config.router_bgp.neighbors:
            identifier = f"{neighbors_item.ip_address}" if neighbors_item.peer is None else f"{neighbors_item.peer} ({neighbors_item.ip_address})"
            peer_groups_item = (
                self.structured_config.router_bgp.peer_groups[neighbors_item.peer_group]
                if neighbors_item.peer_group and neighbors_item.peer_group in self.structured_config.router_bgp.peer_groups
                else None
            )

            # Skip neighbors that are shutdown
            if neighbors_item.shutdown is True:
                LOGGER.debug("<%s> BGP peer %s skipped - Shutdown", self.hostname, identifier)
                continue

            # Skip neighbors in shutdown peer groups
            if peer_groups_item and peer_groups_item.shutdown is True:
                LOGGER.debug("<%s> BGP peer %s skipped - Peer group %s shutdown", self.hostname, identifier, neighbors_item.peer_group)
                continue

            # When peer field is set, check if the peer device is in the fabric and deployed
            if neighbors_item.peer and (
                neighbors_item.peer not in self.minimal_structured_configs or not self.minimal_structured_configs[neighbors_item.peer].is_deployed
            ):
                LOGGER.debug("<%s> BGP peer %s skipped - Peer not in fabric or not deployed", self.hostname, identifier)
                continue

            neighbors.append(
                BgpNeighbor(
                    ip_address=ip_interface(neighbors_item.ip_address).ip,
                    vrf="default",
                    update_source=neighbors_item.update_source or (peer_groups_item.update_source if peer_groups_item else None),
                )
            )

        # Process VRF neighbors
        for vrfs_item in self.structured_config.router_bgp.vrfs:
            vrf_name = vrfs_item.name
            if vrfs_item.validate_bgp_peers is False:
                LOGGER.debug("<%s> BGP peers in VRF %s skipped - validate_bgp_peers disabled", self.hostname, vrf_name)
                continue

            for neighbors_item in vrfs_item.neighbors:
                identifier = f"{neighbors_item.ip_address} (VRF {vrf_name})"
                peer_groups_item = (
                    self.structured_config.router_bgp.peer_groups[neighbors_item.peer_group]
                    if neighbors_item.peer_group and neighbors_item.peer_group in self.structured_config.router_bgp.peer_groups
                    else None
                )

                # Skip neighbors that are shutdown
                if neighbors_item.shutdown is True:
                    LOGGER.debug("<%s> BGP peer %s in VRF %s skipped - Shutdown", self.hostname, identifier, vrf_name)
                    continue

                # Skip neighbors in shutdown peer groups
                if peer_groups_item and peer_groups_item.shutdown is True:
                    LOGGER.debug("<%s> BGP peer %s in VRF %s skipped - Peer group %s shutdown", self.hostname, identifier, vrf_name, neighbors_item.peer_group)
                    continue

                neighbors.append(
                    BgpNeighbor(
                        ip_address=ip_interface(neighbors_item.ip_address).ip,
                        vrf=vrf_name,
                        update_source=neighbors_item.update_source or (peer_groups_item.update_source if peer_groups_item else None),
                    )
                )

        return neighbors

    @cached_property
    def bgp_neighbor_interfaces(self) -> list[BgpNeighborInterface]:
        """Generate a list of BGP neighbor interfaces (RFC5549) for the device."""
        neighbor_interfaces: list[BgpNeighborInterface] = []

        # Process default VRF neighbor interfaces
        for neighbor_interfaces_item in self.structured_config.router_bgp.neighbor_interfaces:
            identifier = (
                f"{neighbor_interfaces_item.name}"
                if neighbor_interfaces_item.peer is None
                else f"{neighbor_interfaces_item.peer} ({neighbor_interfaces_item.name})"
            )

            # Skip neighbor interfaces in shutdown peer groups
            if (
                neighbor_interfaces_item.peer_group in self.structured_config.router_bgp.peer_groups
                and self.structured_config.router_bgp.peer_groups[neighbor_interfaces_item.peer_group].shutdown is True
            ):
                LOGGER.debug("<%s> BGP RFC5549 peer %s skipped - Peer group %s shutdown", self.hostname, identifier, neighbor_interfaces_item.peer_group)
                continue

            # When peer field is set, check if the peer device is in the fabric and deployed
            if neighbor_interfaces_item.peer and (
                neighbor_interfaces_item.peer not in self.minimal_structured_configs
                or not self.minimal_structured_configs[neighbor_interfaces_item.peer].is_deployed
            ):
                LOGGER.debug("<%s> BGP RFC5549 peer %s skipped - Peer not in fabric or not deployed", self.hostname, identifier)
                continue

            neighbor_interfaces.append(BgpNeighborInterface(interface=neighbor_interfaces_item.name, vrf="default"))

        # Process VRF neighbor interfaces
        for vrfs_item in self.structured_config.router_bgp.vrfs:
            vrf_name = vrfs_item.name
            if vrfs_item.validate_bgp_peers is False:
                LOGGER.debug("<%s> BGP RFC5549 peers in VRF %s skipped - validate_bgp_peers disabled", self.hostname, vrf_name)
                continue

            for neighbor_interfaces_item in vrfs_item.neighbor_interfaces:
                identifier = f"{neighbor_interfaces_item.name} (VRF {vrf_name})"

                # Skip neighbor interfaces in shutdown peer groups
                if (
                    neighbor_interfaces_item.peer_group
                    and neighbor_interfaces_item.peer_group in self.structured_config.router_bgp.peer_groups
                    and self.structured_config.router_bgp.peer_groups[neighbor_interfaces_item.peer_group].shutdown is True
                ):
                    LOGGER.debug(
                        "<%s> BGP RFC5549 peer %s in VRF %s skipped - Peer group %s shutdown",
                        self.hostname,
                        identifier,
                        vrf_name,
                        neighbor_interfaces_item.peer_group,
                    )
                    continue

                neighbor_interfaces.append(BgpNeighborInterface(interface=neighbor_interfaces_item.name, vrf=vrf_name))

        return neighbor_interfaces
