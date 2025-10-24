# Copyright (c) 2023-2025 Arista Networks, Inc.
# Use of this source code is governed by the Apache License 2.0
# that can be found in the LICENSE file.
from __future__ import annotations

from logging import getLogger
from time import perf_counter
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ._anta.lib import AntaCatalog
    from ._anta.models import MinimalStructuredConfig
    from .api._anta import AvdCatalogGenerationSettings

LOGGER = getLogger(__name__)


def get_device_test_catalog(
    hostname: str,
    structured_config: dict,
    fabric_data: dict[str, MinimalStructuredConfig],
    settings: AvdCatalogGenerationSettings | None = None,
) -> AntaCatalog:
    """
    Generate an ANTA test catalog for a single device.

    By default, the ANTA catalog will be generated from all tests specified in the AVD test index.

    An optional instance of `pyavd.api._anta.AvdCatalogGenerationSettings` can be provided
    to customize the catalog generation process, such as running only specific tests, or skipping certain tests.

    AVD needs fabric-wide data of all devices to generate the catalog. Make sure to create a single `fabric_data`
    dictionary using `pyavd.api._anta.get_fabric_data` for consistent data across catalog generations.

    Test definitions can be omitted from the catalog if the required data is not available for a specific device.
    You can configure logging and set the log level to DEBUG to see which test definitions are skipped and the reason why.

    Args:
        hostname: The hostname of the device for which the catalog is being generated.
        structured_config: The structured configuration of the device.
            Variables should be converted and validated according to AVD `eos_cli_config_gen` schema first using `pyavd.validate_structured_config`.
        fabric_data: A dictionary keyed by hostname containing a `MinimalStructuredConfig` dataclass instance for each device.
            Must be generated using `pyavd.api._anta.get_fabric_data`.
        settings: Optional settings object to customize the catalog generation process.

    Returns:
        The generated ANTA catalog for the device.
    """
    from dataclasses import asdict  # noqa: PLC0415

    from ._anta.factories import create_catalog  # noqa: PLC0415
    from ._anta.index import AVD_TEST_INDEX, AVD_TEST_NAMES  # noqa: PLC0415
    from ._anta.utils import dump_anta_catalog  # noqa: PLC0415
    from .api._anta import AvdCatalogGenerationSettings  # noqa: PLC0415

    settings = settings or AvdCatalogGenerationSettings()

    start_time = perf_counter()
    LOGGER.debug("<%s> Generating ANTA catalog with settings: %s", hostname, asdict(settings))

    # Check for invalid test names across all filters
    invalid_tests = {
        "run_tests": set(settings.run_tests) - set(AVD_TEST_NAMES),
        "skip_tests": set(settings.skip_tests) - set(AVD_TEST_NAMES),
    }

    for filter_type, invalid_names in invalid_tests.items():
        if invalid_names:
            msg = f"Invalid test names in {filter_type}: {', '.join(invalid_names)}"
            raise ValueError(msg)

    # Remove any tests from run_tests that are in skip_tests
    if settings.run_tests and settings.skip_tests:
        run_tests = [test for test in settings.run_tests if test not in settings.skip_tests]
        LOGGER.debug("<%s> Cleaned up run_tests after removing skipped tests: %s", hostname, run_tests)
    else:
        run_tests = settings.run_tests

    # Filter test specs based on skip_tests and run_tests
    filtered_test_specs = []

    for test in AVD_TEST_INDEX:
        # Skip tests explicitly mentioned in skip_tests
        if test.test_class.name in settings.skip_tests:
            continue
        # If run_tests is specified, only include tests in that set
        if run_tests and test.test_class.name not in run_tests:
            continue

        filtered_test_specs.append(test)

    catalog = create_catalog(hostname, structured_config, fabric_data, settings, filtered_test_specs)

    if settings.output_dir:
        dump_anta_catalog(hostname, catalog, settings.output_dir)

    stop_time = perf_counter()
    LOGGER.debug("<%s> Generated ANTA catalog in %.4f seconds", hostname, stop_time - start_time)

    return catalog
