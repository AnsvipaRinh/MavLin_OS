# MavLinOS installation contract

MavLinOS currently provides an Arch-based live ISO and a project-specific post-install configuration layer. It does **not** yet ship a graphical installer or replace the normal Arch installation procedure.

## Supported installation flow

1. Boot the MavLinOS ISO.
2. Partition, format, mount, install the Arch base system and the packages from the project profile using the normal Arch installation workflow.
3. While still booted into the MavLinOS live environment, with the installed target mounted at `/mnt`, stage the MavLinOS runtime into the target:

    /usr/local/bin/mavericks/mavericks-stage-target.sh /mnt

4. Enter the installed system with `arch-chroot` and run the one-shot post-install configuration:

    arch-chroot /mnt /usr/local/bin/mavericks/mavericks-firstboot.sh

5. Finish the normal Arch installation steps (fstab, bootloader installation/configuration, user account, networking credentials, etc.) and reboot into the target.

## Why staging is explicit

Files under the ISO's `airootfs/` describe the live environment. A manual Arch installation does not automatically copy arbitrary `airootfs` files into the target filesystem. The staging helper therefore makes the boundary explicit instead of pretending that firstboot is automatically installed or invoked.

The helper copies:

- `/usr/local/bin/mavericks/`
- `/usr/local/share/mavericks/profiles/`

It refuses to operate on `/` to avoid accidentally modifying the live environment.

## Firstboot responsibilities

`mavericks-firstboot.sh` is deliberately a post-install configuration step, not an installer. It:

- selects the hardware profile;
- preserves installer-selected hostname and timezone;
- augments existing systemd-boot options without replacing root/crypt/resume parameters;
- applies profile-gated power/network policy;
- enables system services;
- provisions the primary regular user's Mavericks bookmarks;
- enables the packaged per-user timers without requiring an interactive user D-Bus session;
- performs MacBook-specific NVRAM handling only for the `macbook10,1` profile;
- writes `/etc/mavericks/firstboot-complete` as its idempotence marker.

## Current limitation

There is intentionally no claim that firstboot runs automatically after installation. Automatic invocation requires a project-controlled installer integration that does not exist yet. Until that integration is implemented, the explicit staging + `arch-chroot` flow above is the authoritative contract.