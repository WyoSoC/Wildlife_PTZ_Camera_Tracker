#!/usr/bin/env python3
"""
Auto-detecting installer for Eagle Tracker backend dependencies.

Detects the current hardware platform, installs the correct PyTorch variant,
then installs all remaining dependencies from requirements.txt.

Usage:
    python install.py            # auto-detect and install
    python install.py --dry-run  # print commands without running them
    python install.py --list     # show detected platform only
    python install.py --patch    # (Jetson only) re-apply venv patches without reinstalling
"""
from __future__ import annotations
import argparse
import os
import platform
import subprocess
import sys


# ── Platform detection ─────────────────────────────────────────────────────────

def detect_platform() -> str:
    """
    Return one of: 'jetson' | 'cuda' | 'macos' | 'rpi' | 'cpu'

    Detection order:
      1. Jetson  — aarch64 Linux with nvidia-smi present (JetPack CUDA)
      2. CUDA    — any Linux/Windows host where nvidia-smi succeeds
      3. macOS   — Darwin (MPS auto-selected by torch on Apple Silicon)
      4. RPi     — aarch64 / armv7l Linux without CUDA
      5. CPU     — everything else
    """
    system  = platform.system()
    machine = platform.machine()
    cuda    = _command_ok(['nvidia-smi'])

    if system == 'Linux' and machine == 'aarch64' and cuda:
        return 'jetson'
    if system == 'Darwin':
        return 'macos'
    if cuda:
        return 'cuda'
    if machine in ('aarch64', 'armv7l'):
        return 'rpi'
    return 'cpu'


PLATFORM_LABELS: dict[str, str] = {
    'jetson': 'NVIDIA Jetson  (aarch64, CUDA via JetPack 6)',
    'cuda':   'NVIDIA GPU     (Linux/Windows, PyTorch 2.12.1+cu126)',
    'macos':  'macOS          (Apple Silicon MPS or Intel CPU)',
    'rpi':    'Raspberry Pi   (aarch64/armv7l, CPU-only)',
    'cpu':    'Generic CPU    (x86_64, no GPU detected)',
}


# ── PyTorch wheel URLs ─────────────────────────────────────────────────────────

# Jetson Orin (SM 8.7), JetPack 6.1 / R36.4, CUDA 12.6.
# Standard download.pytorch.org aarch64+cu126 builds include only SM 8.0 and
# SM 9.0 — Orin (SM 8.7) fails with "no kernel image available".
# Use NVIDIA's JetPack-specific wheels instead.
# torch 2.5.0a0 NV24.08  <->  torchvision 0.20.0 (cu124 aarch64).
_JETSON_TORCH_URL = (
    "https://developer.download.nvidia.com/compute/redist/jp/v61/pytorch/"
    "torch-2.5.0a0+872d972e41.nv24.08.17622132-cp310-cp310-linux_aarch64.whl"
)
_JETSON_TV_URL = (
    "https://download-r2.pytorch.org/whl/cu124/"
    "torchvision-0.20.0-cp310-cp310-linux_aarch64.whl"
)

# Desktop / server NVIDIA GPU (x86_64, CUDA 12.6).
# SM 8.9 (RTX 4090), SM 8.6 (RTX 3090), SM 9.0 (H100) etc. are all in the
# standard manylinux x86_64 builds.  cu126 keeps parity with the Jetson CUDA.
_CUDA_INDEX_URL = "https://download.pytorch.org/whl/cu126"


# ── Helpers ────────────────────────────────────────────────────────────────────

def _command_ok(cmd: list[str]) -> bool:
    try:
        r = subprocess.run(cmd, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=5)
        return r.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


def _torch_already_installed() -> bool:
    return _command_ok([sys.executable, '-c', 'import torch'])


def _jetson_torch_ok() -> bool:
    """True only if the installed torch was compiled with SM 8.7 (Orin) support."""
    return _command_ok([
        sys.executable, '-c',
        'import torch; assert "sm_87" in torch.cuda.get_arch_list()',
    ])


def _site_packages() -> str:
    r = subprocess.run(
        [sys.executable, '-c',
         'import site; print(site.getsitepackages()[0])'],
        capture_output=True, text=True, timeout=10,
    )
    return r.stdout.strip()


def run(cmd: list[str], dry_run: bool = False) -> None:
    print('  $', ' '.join(cmd))
    if not dry_run:
        subprocess.check_call(cmd)


# ── Jetson venv compatibility patches ─────────────────────────────────────────
#
# The NVIDIA torch 2.5.0a0 JetPack build has subtly different internal APIs
# from what third-party packages compiled against the public torch 2.5.0 expect.
# These patches fix three issues:
#
#   1. torchvision._meta_registrations  — circular import at load time
#   2. ultralytics.utils.nms            — torchvision CUDA NMS is CPU-only on
#                                         aarch64 torchvision 0.20.0
#   3. ultralytics.models.sam.sam3      — eager top-level torchvision import
#                                         crashes startup when ultralytics loads
#
# All patches are idempotent: they check a unique marker string before touching
# the file.  Run install.py --patch to re-apply after a package upgrade.

def _patch_file(path: str, marker: str, old: str, new: str,
                label: str, dry_run: bool) -> None:
    """Replace old→new in path if marker is absent; skip silently if already applied."""
    if not os.path.isfile(path):
        print(f'    skip  {label}: not found (package not installed?)')
        return
    content = open(path, encoding='utf-8').read()
    if marker in content:
        print(f'    ok    {label}')
        return
    if old not in content:
        print(f'    warn  {label}: expected text not found — package may have changed')
        return
    print(f'    patch {label}')
    if not dry_run:
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(content.replace(old, new, 1))


def apply_jetson_patches(dry_run: bool = False) -> None:
    """Apply (or verify) all Jetson compatibility patches in the active venv."""
    print('\n[Jetson venv patches]')
    sp = _site_packages()

    # ── 1. torchvision/_meta_registrations.py ─────────────────────────────────
    tv_meta = os.path.join(sp, 'torchvision', '_meta_registrations.py')

    _patch_file(
        path=tv_meta,
        marker='_has_extension = True',
        old='import torchvision.extension  # noqa: F401',
        new=(
            'try:\n'
            '    import torchvision.extension  # noqa: F401\n'
            '    _has_extension = True\n'
            'except (ImportError, AttributeError):\n'
            '    _has_extension = False'
        ),
        label='torchvision/_meta_registrations.py [import guard]',
        dry_run=dry_run,
    )

    _patch_file(
        path=tv_meta,
        marker='import torchvision.extension as _ext',
        old=(
            '        if torchvision.extension._has_ops():\n'
            '            get_meta_lib().impl(getattr(getattr(torch.ops.torchvision, op_name), overload_name), fn)\n'
            '        return fn'
        ),
        new=(
            '        try:\n'
            '            import torchvision.extension as _ext\n'
            '            if _ext._has_ops():\n'
            '                get_meta_lib().impl(getattr(getattr(torch.ops.torchvision, op_name), overload_name), fn)\n'
            '        except Exception:\n'
            '            pass\n'
            '        return fn'
        ),
        label='torchvision/_meta_registrations.py [lazy register_meta]',
        dry_run=dry_run,
    )

    # ── 2. ultralytics/utils/nms.py ───────────────────────────────────────────
    _patch_file(
        path=os.path.join(sp, 'ultralytics', 'utils', 'nms.py'),
        marker='boxes.is_cuda',
        old='            if "torchvision" in sys.modules:',
        new='            if "torchvision" in sys.modules and not boxes.is_cuda:',
        label='ultralytics/utils/nms.py [CUDA NMS bypass]',
        dry_run=dry_run,
    )

    # ── 3. ultralytics/models/sam/sam3/geometry_encoders.py ───────────────────
    _patch_file(
        path=os.path.join(
            sp, 'ultralytics', 'models', 'sam', 'sam3', 'geometry_encoders.py'
        ),
        marker='SAM3 only',
        old='import torchvision\n',
        new=(
            'try:\n'
            '    import torchvision\n'
            'except Exception:\n'
            '    torchvision = None  # SAM3 only; YOLO inference does not require torchvision\n'
        ),
        label='ultralytics/models/sam/sam3/geometry_encoders.py [deferred import]',
        dry_run=dry_run,
    )


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('--dry-run', action='store_true',
                        help='Print commands without executing them')
    parser.add_argument('--list', action='store_true',
                        help='Print detected platform and exit')
    parser.add_argument('--patch', action='store_true',
                        help='(Jetson) Re-apply venv patches without reinstalling torch')
    args = parser.parse_args()

    pid = detect_platform()
    print(f'\nDetected platform: {PLATFORM_LABELS[pid]}')

    if args.list:
        return

    pip = [sys.executable, '-m', 'pip', 'install']

    # ── --patch shortcut ───────────────────────────────────────────────────────
    if args.patch:
        if pid != 'jetson':
            print('--patch is only needed on Jetson; nothing to do.')
            return
        apply_jetson_patches(args.dry_run)
        return

    # ── Step 1: PyTorch ────────────────────────────────────────────────────────
    print('\n[1/3] PyTorch')
    if pid == 'jetson':
        if _jetson_torch_ok():
            print('  Jetson torch with SM 8.7 already present — skipping install')
        else:
            if _torch_already_installed():
                print('  torch present but missing SM 8.7 — reinstalling Jetson build')
            # torch and torchvision must be installed with --no-deps: the NVIDIA
            # torch wheel version string doesn't match what torchvision requires,
            # and the standard CUDA libs in requirements conflict with JetPack's.
            run(pip + ['--force-reinstall', '--no-deps', _JETSON_TORCH_URL],
                args.dry_run)
            run(pip + ['--force-reinstall', '--no-deps', _JETSON_TV_URL],
                args.dry_run)
            # NVIDIA torch 2.5.0a0 was compiled against numpy 1.x.
            run(pip + ['numpy<2.0'], args.dry_run)

    else:
        if _torch_already_installed():
            print('  torch already present — skipping')
        else:
            if pid == 'cuda':
                run(pip + ['torch', 'torchvision',
                            '--index-url', _CUDA_INDEX_URL], args.dry_run)
            else:
                # macOS (MPS), Raspberry Pi, plain CPU
                run(pip + ['torch', 'torchvision'], args.dry_run)

    # ── Step 2: Remaining dependencies ────────────────────────────────────────
    print('\n[2/3] Remaining dependencies (requirements.txt)')
    req = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'requirements.txt')
    run(pip + ['-r', req], args.dry_run)

    # ── Step 3: Jetson venv patches ────────────────────────────────────────────
    if pid == 'jetson':
        apply_jetson_patches(args.dry_run)

    print('\nInstallation complete.')
    print('To start the server:')
    print('  uvicorn backend.main:app --host 0.0.0.0 --port 9090 --reload\n')


if __name__ == '__main__':
    main()
