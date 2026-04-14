# Copyright (c) 2023-2026 Arista Networks, Inc.
# Use of this source code is governed by the Apache License 2.0
# that can be found in the LICENSE file.
from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Iterable


class ConfigletRefProtocol(Protocol):
    """A reference to a configlet by name within a container."""

    name: str


class ConfigletProtocol(Protocol):
    """A configlet with a name and file path."""

    name: str
    file: str


class ContainerProtocol(Protocol):
    """A container with attributes and iterable sub-containers."""

    name: str
    tag_query: str
    description: str | None
    match_policy: str
    configlets: Iterable[ConfigletRefProtocol]
    sub_containers: Iterable[ContainerProtocol]
