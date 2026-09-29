"""MacBook10,1 backend — documented stub (NOT wired to production).

This backend is a placeholder for future hardware validation on the real
MacBook10,1. It documents the intended boot-selection mechanism
(efibootmgr -n/-o, systemd-boot entries) but does NOT modify any
production bootloader state.

Per the task spec: "Mac backend documented only (do NOT modify production
bootloader)."
"""
class MacBackend:
    """Documented stub for MacBook10,1 hardware validation.

    Intended boot selection (requires root + efibootmgr):
        efibootmgr -n <bootnum>   # BootNext (one-shot)
        efibootmgr -o <order>     # persistent boot order

    Intended reboot: systemctl reboot
    Intended shutdown: systemctl poweroff

    NOT IMPLEMENTED — this stub raises NotImplementedError for all
    operations. It exists so scenario YAMLs can list `mac10_1` as a
    future backend without breaking the runner.
    """

    def __init__(self, *args, **kwargs):
        raise NotImplementedError(
            "MacBackend is a documented stub for future MacBook10,1 hardware "
            "validation. It does not modify production bootloader state. "
            "See docs/LAB_HARNESS.md for the intended efibootmgr-based design."
        )
