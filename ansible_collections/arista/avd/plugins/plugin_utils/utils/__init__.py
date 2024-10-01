# Copyright (c) 2023-2024 Arista Networks, Inc.
# Use of this source code is governed by the Apache License 2.0
# that can be found in the LICENSE file.
from ansible_collections.arista.avd.plugins.plugin_utils.pyavd_wrappers import RaiseOnUse

from .compile_searchpath import compile_searchpath
from .cprofile_decorator import cprofile
from .get_templar import get_templar
from .get_validated_path import get_validated_path
from .get_validated_value import get_validated_value
from .log_message import log_message
from .python_to_ansible_logging_handler import PythonToAnsibleContextFilter, PythonToAnsibleHandler
from .write_file import write_file
from .yaml_dumper import NoAliasDumper, YamlDumper
from .yaml_loader import YamlLoader

# TODO: The pyavd imports can be removed once validate_state has been moved to pyavd.
try:
    from pyavd._utils import default, get, get_item
except ImportError as e:
    default = get = RaiseOnUse(ImportError(f"The 'arista.avd' collection requires the 'pyavd' Python library. Got import error {e}"))

__all__ = [
    "compile_searchpath",
    "get_templar",
    "log_message",
    "PythonToAnsibleContextFilter",
    "PythonToAnsibleHandler",
    "NoAliasDumper",
    "get_validated_path",
    "get_validated_value",
    "cprofile",
    "YamlDumper",
    "YamlLoader",
    "default",
    "get",
    "get_item",
    "write_file",
]
