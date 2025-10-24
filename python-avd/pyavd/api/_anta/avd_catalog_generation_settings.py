# Copyright (c) 2023-2025 Arista Networks, Inc.
# Use of this source code is governed by the Apache License 2.0
# that can be found in the LICENSE file.
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True)
class AvdCatalogGenerationSettings:
    """
    Model defining settings for the AVD-generated ANTA catalog.

    Used in `pyavd.get_device_test_catalog` to customize the AVD test catalog generation.
    """

    run_tests: list[str] = field(default_factory=list)
    """List of ANTA test names to run. Other tests are skipped."""
    skip_tests: list[str] = field(default_factory=list)
    """List of ANTA test names to skip. Takes precedence over `run_tests`."""
    output_dir: str | Path | None = field(default=None)
    """Directory where to dump the generated ANTA catalog."""
    allow_bgp_vrfs: bool = field(default=False)
    """Whether to include BGP neighbors in VRFs for testing."""
