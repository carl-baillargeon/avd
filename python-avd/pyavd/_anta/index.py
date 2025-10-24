# Copyright (c) 2023-2025 Arista Networks, Inc.
# Use of this source code is governed by the Apache License 2.0
# that can be found in the LICENSE file.
"""Test index for PyAVD ANTA tests."""

from __future__ import annotations

from pyavd._anta.input_factories import *
from pyavd._anta.lib.tests import *

from .constants import StructuredConfigKey
from .models import AntaTestSpec

AVD_TEST_INDEX: list[AntaTestSpec] = [
    AntaTestSpec(
        test_class=VerifyAgentLogs,
    ),
    AntaTestSpec(
        test_class=VerifyAPIHttpsSSL,
        conditional_keys=[StructuredConfigKey.HTTPS_SSL_PROFILE],
        input_factory=VerifyAPIHttpsSSLInputFactory,
    ),
    AntaTestSpec(
        test_class=VerifyAVTSpecificPath,
        conditional_keys=[StructuredConfigKey.ROUTER_AVT, StructuredConfigKey.ROUTER_PATH_SELECTION],
        input_factory=VerifyAVTSpecificPathInputFactory,
    ),
    AntaTestSpec(
        test_class=VerifyBGPPeerSession,
        conditional_keys=[StructuredConfigKey.ROUTER_BGP],
        input_factory=VerifyBGPPeerSessionInputFactory,
    ),
    AntaTestSpec(
        test_class=VerifyCoredump,
    ),
    AntaTestSpec(
        test_class=VerifyEnvironmentCooling,
        input_factory=VerifyEnvironmentCoolingInputFactory,
    ),
    AntaTestSpec(
        test_class=VerifyEnvironmentPower,
        input_factory=VerifyEnvironmentPowerInputFactory,
    ),
    AntaTestSpec(
        test_class=VerifyEnvironmentSystemCooling,
    ),
    AntaTestSpec(
        test_class=VerifyFileSystemUtilization,
    ),
    AntaTestSpec(
        test_class=VerifyIllegalLACP,
        conditional_keys=[StructuredConfigKey.PORT_CHANNEL_INTERFACES],
    ),
    AntaTestSpec(
        test_class=VerifyInterfaceDiscards,
    ),
    AntaTestSpec(
        test_class=VerifyInterfaceErrDisabled,
    ),
    AntaTestSpec(
        test_class=VerifyInterfaceErrors,
    ),
    AntaTestSpec(
        test_class=VerifyInterfaceUtilization,
    ),
    AntaTestSpec(
        test_class=VerifyInterfacesStatus,
        input_factory=VerifyInterfacesStatusInputFactory,
    ),
    AntaTestSpec(
        test_class=VerifyInventory,
    ),
    AntaTestSpec(
        test_class=VerifyPortChannels,
        conditional_keys=[StructuredConfigKey.PORT_CHANNEL_INTERFACES],
        input_factory=VerifyPortChannelsInputFactory,
    ),
    AntaTestSpec(
        test_class=VerifyRunningConfigDiffs,
    ),
    AntaTestSpec(
        test_class=VerifyStormControlDrops,
    ),
    AntaTestSpec(
        test_class=VerifyLLDPNeighbors,
        conditional_keys=[StructuredConfigKey.ETHERNET_INTERFACES],
        input_factory=VerifyLLDPNeighborsInputFactory,
    ),
    AntaTestSpec(
        test_class=VerifyLoggingErrors,
    ),
    AntaTestSpec(
        test_class=VerifyMaintenance,
    ),
    AntaTestSpec(
        test_class=VerifyMemoryUtilization,
    ),
    AntaTestSpec(
        test_class=VerifyMlagConfigSanity,
        conditional_keys=[StructuredConfigKey.MLAG_CONFIGURATION],
    ),
    AntaTestSpec(
        test_class=VerifyMlagInterfaces,
        conditional_keys=[StructuredConfigKey.MLAG_CONFIGURATION],
    ),
    AntaTestSpec(
        test_class=VerifyMlagStatus,
        conditional_keys=[StructuredConfigKey.MLAG_CONFIGURATION],
    ),
    AntaTestSpec(
        test_class=VerifyNTP,
    ),
    AntaTestSpec(
        test_class=VerifySpecificPath,
        conditional_keys=[StructuredConfigKey.ROUTER_PATH_SELECTION],
        input_factory=VerifySpecificPathInputFactory,
    ),
    AntaTestSpec(
        test_class=VerifyReachability,
        input_factory=VerifyReachabilityInputFactory,
    ),
    AntaTestSpec(
        test_class=VerifyReloadCause,
        input_factory=VerifyReloadCauseInputFactory,
    ),
    AntaTestSpec(
        test_class=VerifyRoutingProtocolModel,
        conditional_keys=[StructuredConfigKey.SERVICE_ROUTING_PROTOCOLS_MODEL],
        input_factory=VerifyRoutingProtocolModelInputFactory,
    ),
    AntaTestSpec(
        test_class=VerifySpecificIPSecConn,
        conditional_keys=[StructuredConfigKey.ROUTER_PATH_SELECTION],
        input_factory=VerifySpecificIPSecConnInputFactory,
    ),
    AntaTestSpec(
        test_class=VerifySTPCounters,
    ),
    AntaTestSpec(
        test_class=VerifyTemperature,
    ),
    AntaTestSpec(
        test_class=VerifyTransceiversTemperature,
    ),
    AntaTestSpec(test_class=VerifyVxlanConfigSanity, conditional_keys=[StructuredConfigKey.VXLAN1_INTERFACE]),
    AntaTestSpec(
        test_class=VerifyZeroTouch,
    ),
]
"""List of all ANTA tests with their specifications that AVD will run by default."""

AVD_TEST_INDEX.sort(key=lambda x: x.test_class.name)
"""Sort the test index by the test class name."""

AVD_TEST_NAMES: list[str] = [test.test_class.name for test in AVD_TEST_INDEX]
"""List of all available ANTA test names that AVD will run by default."""
