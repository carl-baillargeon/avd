# Copyright (c) 2025 Arista Networks, Inc.
# Use of this source code is governed by the Apache License 2.0
# that can be found in the LICENSE file.
from collections.abc import Iterator
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from dataclasses import dataclass, field
from json import dumps as json_dumps
from json import loads as json_loads
from multiprocessing import cpu_count, get_context
from pathlib import Path
from time import perf_counter
from typing import Any, Literal

from ansible_collections.arista.avd.plugins.plugin_utils.utils import ActionPluginVars
from ansible_collections.arista.avd.plugins.plugin_utils.utils.avd_action_plugin import AvdActionPlugin, AvdLoggingConfig

try:
    from pyavd_utils.validation import get_validated_data, init_store_from_file

    from pyavd._errors import AvdDeprecationWarning, AvdValidationError
    from pyavd._utils import get, strip_empties_from_dict
    from pyavd.avd_schema_tools import EosDesignsAvdSchemaTools

    HAS_PYAVD = True
except ImportError:
    HAS_PYAVD = False


@dataclass(frozen=True, slots=True)
class TemplateWorkerResult:
    """Result from Phase 1 (templating and serializing)."""

    host: str
    templated_json: str | None = None
    worker_error: str | None = None


@dataclass(frozen=True, slots=True)
class ValidateWorkerResult:
    """Result from Phase 2 (validation)."""

    host: str
    validated_json: str | None = None
    worker_error: str | None = None
    validation_errors: tuple[AvdValidationError, ...] = field(default_factory=tuple)
    deprecations: tuple[AvdDeprecationWarning, ...] = field(default_factory=tuple)


PLUGIN_NAME = "arista.avd.eos_designs_builder"

TARGET_LOGGERS = ["ansible_collections.arista.avd", "included_store", "validation"]

ARGUMENT_SPEC = {
    "output_dir": {"type": "str", "required": True},
    # TODO: Need to figure out the proper default batch size.
    "batch_size": {"type": "int", "default": 10},
    "validation_mode": {"type": "str", "choices": ["error", "warning"], "default": "error"},
}

_HOSTVARS_MANAGER: ActionPluginVars | None = None


def set_worker_context(hostvars: ActionPluginVars) -> None:
    """
    Set the global worker context.

    Must be called by the parent process before forking.
    """
    global _HOSTVARS_MANAGER  # noqa: PLW0603
    _HOSTVARS_MANAGER = hostvars


def get_worker_hostvars() -> ActionPluginVars:
    """Retrieve hostvars in the worker process."""
    if _HOSTVARS_MANAGER is None:
        msg = "Worker context not initialized. 'set_worker_context' was not called before forking."
        raise RuntimeError(msg)
    return _HOSTVARS_MANAGER


class ActionModule(AvdActionPlugin):
    _logging_config = AvdLoggingConfig(target_loggers=TARGET_LOGGERS)

    def main(self, task_vars: dict[str, Any]) -> None:
        if not HAS_PYAVD:
            msg = f"The {PLUGIN_NAME} plugin requires the 'pyavd' Python library. Got import error"
            raise ImportError(msg)

        # Get task arguments and validate them.
        _validation_result, validated_args = self.validate_argument_spec(ARGUMENT_SPEC)
        validated_args = strip_empties_from_dict(validated_args)

        # Converting to JSON and back to remove any AnsibeUnsafe types.
        plugin_args = json_loads(json_dumps(validated_args))

        output_dir = get(plugin_args, "output_dir")
        batch_size = get(plugin_args, "batch_size")
        validation_mode = get(plugin_args, "validation_mode")
        ansible_forks = task_vars.get("ansible_forks", 5)

        groups = task_vars.get("groups", {})
        fabric_name = self._templar.template(task_vars.get("fabric_name", ""))
        fabric_hosts = groups.get(fabric_name, [])
        ansible_play_hosts_all = task_vars.get("ansible_play_hosts_all", [])

        # Check if fabric_name is set and that all play hosts are part Ansible group set in "fabric_name".
        if fabric_name is None or not set(ansible_play_hosts_all).issubset(fabric_hosts):
            msg = (
                "Invalid/missing 'fabric_name' variable. "
                "All hosts in the play must have the same 'fabric_name' value "
                "which must point to an Ansible Group containing the hosts."
                f"play_hosts: {ansible_play_hosts_all}"
            )
            raise ValueError(msg)

        # Cap MP workers at CPU count - 1 (leave one for main/OS), but at least 1.
        # Also cap at number of hosts to avoid creating idle process for small inventories.
        # TODO: Need to honor ansible_forks for MP workers as well (if it's lower than CPU count).
        available_cores = max(1, cpu_count() - 1)
        mp_workers = min(available_cores, len(fabric_hosts)) or 1
        mp_ctx = get_context("fork")

        self.logger.info("Starting execution with %d multiprocessing workers and %d threads", mp_workers, ansible_forks)

        set_worker_context(ActionPluginVars(self))

        # Phase 1: Templating using multiprocessing.
        phase_1_start = perf_counter()

        with ProcessPoolExecutor(max_workers=mp_workers, mp_context=mp_ctx) as process_pool:
            results_iterator = process_pool.map(_template_host_worker, fabric_hosts, chunksize=batch_size)
            templated_data = self._handle_template_results(results_iterator)

        self.logger.info("Phase 1 complete in %.2fs", perf_counter() - phase_1_start)

        # Phase 2: Validation using multithreading.
        if templated_data:
            phase_2_start = perf_counter()

            # Dump store to a file and initialize it.
            schemas_path = Path(output_dir) / "schemas.json"
            schema_tool = EosDesignsAvdSchemaTools()
            schema_tool.avdschema.dump_store(output_path=schemas_path, gzip_output=False)
            init_store_from_file(file=schemas_path)

            with ThreadPoolExecutor(max_workers=ansible_forks) as thread_pool:
                results_iterator = thread_pool.map(_validate_host_worker, templated_data)
                validated_data = self._handle_validate_results(results_iterator, validation_mode)

            self.logger.info("Phase 2 complete in %.2fs", perf_counter() - phase_2_start)

            if validated_data and not self.result.get("failed", False):
                phase_3_start = perf_counter()
                self._write_validated_data(validated_data, output_dir)
                self.logger.info("Phase 3 complete in %.2fs", perf_counter() - phase_3_start)

    def _handle_template_results(self, results: Iterator[TemplateWorkerResult]) -> list[tuple[str, str]]:
        """Process results from Phase 1 workers."""
        templated_data = []

        for result in results:
            # Handle worker failure.
            if result.worker_error:
                self.result["failed"] = True
                self.logger.error("%s: %s", result.host, result.worker_error)
                continue

            if result.templated_json:
                templated_data.append((result.host, result.templated_json))

        return templated_data

    def _handle_validate_results(self, results: Iterator[ValidateWorkerResult], validation_mode: Literal["warning", "error"]) -> list[tuple[str, str]]:
        """Process results from Phase 2 workers."""
        data_validation_errors = 0
        validated_data = []

        for result in results:
            # Handle worker failure.
            if result.worker_error:
                self.result["failed"] = True
                self.logger.error("%s: %s", result.host, result.worker_error)
                continue

            # Handle deprecations.
            for deprecation in result.deprecations:
                # TODO: Deprecations do not seem to return properly from pyavd-utils.
                self.result.setdefault("deprecations", []).append(
                    {
                        "msg": f"{result.host}: {deprecation}",
                        "version": deprecation.version,
                        "date": deprecation.date,
                        "collection_name": "arista.avd",
                        "removed": deprecation.removed,
                    }
                )

            # Handle schema validation errors.
            if result.validation_errors:
                # TODO: Remove validation_mode.
                self.result["failed"] = True

                for validation_error in result.validation_errors:
                    message = f"{result.host}: {validation_error}"
                    if validation_mode == "warning":
                        self.logger.warning(message)
                    else:
                        self.logger.error(message)

                data_validation_errors += len(result.validation_errors)
                continue

            # If successful, buffer the result for writing later.
            if result.validated_json:
                validated_data.append((result.host, result.validated_json))

        if data_validation_errors > 0:
            self.result["msg"] = f"{data_validation_errors} errors found during schema validation of input vars."
            return []

        return validated_data

    def _write_validated_data(self, data: list[tuple[str, str]], output_dir: str) -> None:
        """Write the validated results to disk."""
        # TODO: Validate that output_dir exists.
        output_dir_path = Path(output_dir)

        for host, validated_json in data:
            if validated_json:
                try:
                    dest_path = output_dir_path / f"{host}.json"
                    # TODO: Only write if something changed.
                    dest_path.write_text(validated_json, encoding="utf-8")

                    # Update result dictionary for Ansible output.
                    self.result[host] = {"output": str(dest_path)}
                except OSError:
                    self.result["failed"] = True
                    self.logger.exception("%s: Error while writing validated inputs to %s", host, str(dest_path))


def _template_host_worker(host: str) -> TemplateWorkerResult:
    """Phase 1 worker (MP): Template and serialize variables as JSON for a single host."""
    # Default state.
    templated_json = None
    worker_error = None

    try:
        hostvars_manager = get_worker_hostvars()
        host_hostvars = dict(hostvars_manager[host])
        # TODO: Use a filtered_map to skip certain keys from being templated.
        templated_json = json_dumps(host_hostvars)
    except (TypeError, ValueError, RecursionError) as e:
        worker_error = f"Serialization error in worker process: {e}"
    except Exception as e:
        worker_error = f"Unexpected error in templating worker process: {e}"

    return TemplateWorkerResult(host=host, templated_json=templated_json, worker_error=worker_error)


def _validate_host_worker(host_and_json: tuple[str, str]) -> ValidateWorkerResult:
    """Phase 2 worker (MT): Validate JSON string (Rust) for a single host."""
    host, templated_json = host_and_json

    # Default state.
    validated_json = None
    worker_error = None
    validation_errors: tuple[AvdValidationError, ...] = ()
    deprecations: tuple[AvdDeprecationWarning, ...] = ()

    try:
        # Validation in Rust, releasing the GIL.
        validated_data_result = get_validated_data(templated_json, "eos_designs")

        if validated_data_result.validation_result.violations:
            validation_errors = tuple(AvdValidationError.from_violation(violation) for violation in validated_data_result.validation_result.violations)
        if validated_data_result.validation_result.deprecations:
            deprecations = tuple(AvdDeprecationWarning.from_deprecation(deprecation) for deprecation in validated_data_result.validation_result.deprecations)

        # Store the output data in the result object.
        if validated_data_result.validated_data is not None:
            # TODO: Write files here using Ansible native tmp structure.
            validated_json = validated_data_result.validated_data

    except Exception as e:
        worker_error = f"Unexpected error in validation worker thread: {e}"

    return ValidateWorkerResult(
        host=host,
        validated_json=validated_json,
        worker_error=worker_error,
        validation_errors=validation_errors,
        deprecations=deprecations,
    )
