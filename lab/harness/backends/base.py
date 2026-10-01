"""Target backend abstraction for the mavericks-lab harness.

A TargetBackend represents a bootable target (QEMU guest, simulated
virtual-target, or future MacBook10,1). Scenarios are written against
this narrow API so the same scenario YAML runs on any backend.

Narrow boot-selection API (per task spec):
    get_boot_state() -> {current_slot, next_slot}
    select_boot(slot)
    reboot()
    shutdown()
"""
from abc import ABC, abstractmethod


class TargetBackend(ABC):
    @abstractmethod
    def start(self):
        """Boot the target. Returns when the boot oneshot completes."""

    @abstractmethod
    def stop(self, sigkill=False):
        """Shutdown (graceful) or power-loss (sigkill) the target."""

    @abstractmethod
    def run_agent_cmd(self, cmd, args=None, timeout=60):
        """Execute an agent command, return the NDJSON response dict."""

    @abstractmethod
    def read_serial(self):
        """Return the serial log contents (ground truth)."""

    @abstractmethod
    def get_boot_state(self):
        """Return {current_slot, next_slot}."""

    @abstractmethod
    def read_journal(self):
        """Return the agent journal entries."""

    @abstractmethod
    def read_state(self):
        """Return the agent state dict."""

    @abstractmethod
    def write_deploy_image(self, name, data):
        """Write an image to the DATA deploy-inbox."""

    @abstractmethod
    def inject(self, action, **kw):
        """Failure injection (network_down, agent_off, corrupt_rootfs, etc.)."""

    @abstractmethod
    def wait_for_agent_ready(self, timeout=30):
        """Wait for agent to be responsive on command channel after boot.
        Returns True if ready, raises HarnessError on timeout with clear message.
        """
