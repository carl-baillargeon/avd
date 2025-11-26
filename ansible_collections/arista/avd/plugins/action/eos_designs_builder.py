# Copyright (c) 2025 Arista Networks, Inc.
# Use of this source code is governed by the Apache License 2.0
# that can be found in the LICENSE file.
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from json import dumps as json_dumps
from json import loads as json_loads
from logging import Logger
from multiprocessing import get_context
from os import getpid
from pathlib import Path
from threading import current_thread
from time import perf_counter
from typing import Any

from ansible_collections.arista.avd.plugins.plugin_utils.utils import ActionPluginVars
from ansible_collections.arista.avd.plugins.plugin_utils.utils.avd_action_plugin import AvdActionPlugin

try:
    from pyavd._utils import get, strip_empties_from_dict
    from pyavd_utils.validation import get_validated_data  # noqa: F401  # pylint: disable=unused-import

    HAS_PYAVD = True
except ImportError:
    HAS_PYAVD = False

PLUGIN_NAME = "arista.avd.eos_designs_builder"

ARGUMENT_SPEC = {
    "output_dir": {"type": "str", "required": True},
    # TODO: Need to figure out the proper default batch size.
    "batch_size": {"type": "int", "default": 25},
}

# Global variables to share data between processes. Since the plugin is forked, these variables are inherited by child processes.
HOSTVARS_MANAGER: ActionPluginVars | None = None
LOGGER: Logger | None = None


class ActionModule(AvdActionPlugin):
    def main(self, task_vars: dict[str, Any]) -> None:
        global HOSTVARS_MANAGER, LOGGER  # noqa: PLW0603

        # This is an "Ansible Hostvars Manager"-like object where we can retrieve hostvars for each host on-demand.
        # This is special because it contains role, play and task vars as well.
        HOSTVARS_MANAGER = ActionPluginVars(self)

        # Make our special instance logger global so that child processes can use it.
        # TODO: Add proper support for multiprocessing logging in AvdActionPlugin.
        LOGGER = self.logger

        if not HAS_PYAVD:
            msg = f"The {PLUGIN_NAME} plugin requires the 'pyavd' Python library. Got import error"
            raise ImportError(msg)

        ansible_forks = task_vars.get("ansible_forks", 5)

        # Get task arguments and validate them.
        _validation_result, validated_args = self.validate_argument_spec(ARGUMENT_SPEC)
        validated_args = strip_empties_from_dict(validated_args)

        # Converting to json and back to remove any AnsibeUnsafe types.
        plugin_args = json_loads(json_dumps(validated_args))

        output_dir = get(plugin_args, "output_dir")
        batch_size = get(plugin_args, "batch_size")
        ansible_forks = task_vars.get("ansible_forks", 5)

        # Extract inventory information.
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

        # Create batches of hostnames. Cast to str() to avoid pickling AnsibleTaggedStr objects.
        host_batches = [[str(host) for host in fabric_hosts[i : i + batch_size]] for i in range(0, len(fabric_hosts), batch_size)]

        mp_ctx = get_context("fork")
        mp_workers = max((ansible_forks - 1), 1)

        LOGGER.info(
            "Starting execution with %d multiprocessing workers (CPU) and %d multithreading workers (I/O). Processing %d batches.",
            mp_workers,
            ansible_forks,
            len(host_batches),
        )

        # TODO: Need to figure out the proper numbers for the amount of workers for each pool.
        with ProcessPoolExecutor(max_workers=mp_workers, mp_context=mp_ctx) as process_pool, ThreadPoolExecutor(max_workers=ansible_forks) as thread_pool:
            # Serialization with multiprocessing.
            # Submit batches to the process pool. Workers will template hostvars and return serialized JSON.
            serialize_futures = {process_pool.submit(serialize_batch_worker, batch): batch for batch in host_batches}

            validation_futures = []

            # Validation with multithreading.
            # As soon as a batch is serialized, retrieve it and submit to the thread pool.
            # TODO: See if it's "better" to avoid sending the JSON data back to the main process and do the validation/write inside the child processes.
            for future in as_completed(serialize_futures):
                # TODO: Handle exceptions.
                batch_results = future.result()
                for host, json_str in batch_results.items():
                    # If serialization failed for a specific host, we skip validation.
                    if json_str is None:
                        self.result["failed"] = True
                        LOGGER.error("Skipping validation for host %s due to serialization failure.")
                        continue

                    # Submit valid JSON to the thread pool for validation in Rust and file writing.
                    validation_future = thread_pool.submit(validate_and_write_worker, host, json_str, output_dir)
                    validation_futures.append(validation_future)

            # Finalize the pipeline.
            # Wait for all file writes to complete and collect results.
            for future in as_completed(validation_futures):
                # TODO: Handle exceptions.
                host, path = future.result()
                # TODO: Improve final result.
                self.result[host] = {"dest": path, "status": "success"}


def serialize_batch_worker(hostnames: list[str]) -> dict[str, str | None]:
    """
    Multiprocessing worker function.

    Template hostvars for a batch of hosts and serialize them to JSON.
    """
    # Satisfy type checkers.
    if HOSTVARS_MANAGER is None or LOGGER is None:
        msg = "Global variables were not initialized in parent process."
        raise RuntimeError(msg)

    # Get current Process ID for debugging.
    pid = getpid()
    start_time = perf_counter()

    LOGGER.debug("Worker PID %s | Starting serialization for batch of %d hosts: %s", pid, len(hostnames), hostnames)

    results: dict[str, str | None] = {}

    for host in hostnames:
        # TODO: Improve exception handling.
        try:
            # Retrieve the HostVarsVars object and convert to dict.
            # This triggers the heavy CPU work of templating.
            host_vars_data = dict(HOSTVARS_MANAGER[host])

            # Serialize immediately to free up memory before moving to next host.
            results[host] = json_dumps(host_vars_data, indent=4)
        except Exception:  # noqa: PERF203
            results[host] = None

    elapsed = perf_counter() - start_time
    LOGGER.debug("Worker PID %s | Finished batch serialization in %.4f seconds.", pid, elapsed)

    return results


def validate_and_write_worker(hostname: str, json_data: str, output_dir: str) -> tuple[str, str]:
    """
    Multithreading worker function.

    Validate the data using Rust bindings (releasing GIL) and write to disk.
    """
    if LOGGER is None:
        msg = "Global LOGGER not initialized."
        raise RuntimeError(msg)

    # Get current Thread Name for debugging.
    thread_name = current_thread().name
    start_time = perf_counter()

    LOGGER.debug("Thread %s | Starting validation for host %s", thread_name, hostname)

    # Perform validation in Rust using pyavd-utils.
    # validated_data = get_validated_data(json_data, "eos_designs")  # noqa: ERA001
    validated_data = json_data

    file_path = Path(output_dir) / f"{hostname}.json"

    with file_path.open(mode="w", encoding="UTF-8") as file:
        file.write(validated_data)

    elapsed = perf_counter() - start_time
    LOGGER.debug("Thread %s | Finished %s in %.4f seconds.", thread_name, hostname, elapsed)

    return hostname, str(file_path)
