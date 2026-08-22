#!/usr/bin/python3

# SPDX-FileCopyrightText: Copyright 2025-2026 The Secureblue Authors
#
# SPDX-License-Identifier: Apache-2.0

"""Common data for kernel argument hardening."""

import os
import subprocess
import sys
import tomllib
from collections.abc import Sequence

from shared.secure_boot import Bootloader
from utils import BootcBackend

with open("/usr/lib/bootc/kargs.d/10-secureblue.toml", "rb") as f:
    DEFAULT_KARGS = tomllib.load(f)["kargs"]

try:
    with open("/usr/lib/bootc/kargs.d/20-nvidia.toml", "rb") as f:
        IMAGE_NVIDIA_KARGS = tomllib.load(f)["kargs"]
except FileNotFoundError:
    IMAGE_NVIDIA_KARGS = None

DISABLE_32_BIT = "ia32_emulation=0"

FORCE_NOSMT = "nosmt=force"

UNSTABLE_KARGS = [
    "amd_iommu=force_isolation",
    "bdev_allow_write_mounted=0",
    "debugfs=off",
    "efi=disable_early_pci_dma",
    "gather_data_sampling=force",
    "mem_encrypt=on",
    "oops=panic",
]


def apply_kargs(*, add: Sequence[str], remove: Sequence[str]) -> None:
    """Add and remove kernel arguments. Ignores remove kargs if not set."""
    bootc_backend = BootcBackend.from_running()
    bootloader = Bootloader.from_running()

    if bootc_backend == BootcBackend.COMPOSEFS and bootloader == Bootloader.SYSTEMD_BOOT:
        avail_addons_path = "/usr/share/secureblue/uki/addons"
        loaded_addons_path = "/boot/loader/addons"

        addon_suffix = ".addon.efi"
        set_addons = [karg.replace("=", "__") + addon_suffix for karg in add]
        rem_addons = [karg.replace("=", "__") + addon_suffix for karg in remove]

        avail_addons = os.listdir(path=avail_addons_path)
        unavail_addons = [addon for addon in set_addons if addon not in avail_addons]
        if unavail_addons:
            print(f"No such addon(s): {', '.join(unavail_addons)}")
            sys.exit(1)

        # Set kargs
        if add:
            set_addons_path = f"{avail_addons_path}/{{{','.join(set_addons)}}}"
            set_kargs_cmd = f"/usr/bin/cp {set_addons_path} {loaded_addons_path}"
        else:
            set_kargs_cmd = ":"

        # Remove kargs
        if remove:
            rem_addons_path = f"{loaded_addons_path}/{{{','.join(rem_addons)}}}"
            rem_kargs_cmd = f"/usr/bin/rm -f {rem_addons_path}"
        else:
            rem_kargs_cmd = ":"

        run0_cmd = ["/usr/bin/run0", "--via-shell", "eval"]
        mkdir_cmd = f"/usr/bin/mkdir -p {loaded_addons_path}"
        action = f"'{mkdir_cmd} && {set_kargs_cmd} && {rem_kargs_cmd}'"
        print("You must be authorized as an administrator to set/remove kargs.")
        subprocess.run([*run0_cmd, action], check=True)

    elif bootc_backend == BootcBackend.OSTREE and bootloader == Bootloader.GRUB2:
        rpm_ostree_cmd = ["/usr/bin/rpm-ostree", "kargs"]
        for karg in add:
            rpm_ostree_cmd.append(f"--append-if-missing={karg}")
        for karg in remove:
            rpm_ostree_cmd.append(f"--delete-if-present={karg}")
        subprocess.run(rpm_ostree_cmd, check=True)

    else:
        print(f"Unexpected bootc backend and bootloader combination: {bootc_backend}, {bootloader}")
        sys.exit(1)
