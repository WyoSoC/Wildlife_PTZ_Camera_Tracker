#!/usr/bin/env python3
"""
Auto-detecting installer for Eagle Tracker backend dependencies.

Detects the current hardware platform, installs the correct PyTorch variant,
then installs all remaining dependencies from requirements.txt.

Usage:
    python install.py            # auto-detect and install
    python install.py --dry-run  # print commands without running them
    python install.py --list     # show detected platform only
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
    system  = platform.system()   # 'Linux' | 'Darwin' | 'Windows'
    machine = platform.machine()  # 'x86_64' | 'aarch64' | 'arm64' | 'armv7l'
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
    'cuda':   'NVIDIA GPU     (Linux/Windows, CUDA 12.4)',
    'macos':  'macOS          (Apple Silicon MPS or Intel CPU)',
    'rpi':    'Raspberry Pi   (aarch64/armv7l, CPU-only)',
    'cpu':    'Generic CPU    (x86_64, no GPU detected)',
}


# ── PyTorch install specs ──────────────────────────────────────────────────────

def torch_install_args(platform_id: str) -> list[str]:
    """
    Return pip install arguments for the torch/torchvision packages appropriate
    for platform_id.  The caller prepends [sys.executable, '-m', 'pip', 'install'].
    """
    base = ['torch', 'torchvision']

    if platform_id == 'jetson':
        # JetPack 6 / CUDA 12.6 wheels — official PyTorch index for aarch64+cu126.
        # (pypi.jetson-ai-lab.dev no longer resolves as of mid-2026.)
        return base + ['--index-url', 'https://download.pytorch.org/whl/cu126']

    if platform_id == 'cuda':
        # Desktop / laptop NVIDIA — CUDA 12.4 wheels.
        # For older drivers (CUDA 11.8) change cu124 → cu118.
        return base + ['--index-url', 'https://download.pytorch.org/whl/cu124']

    # macOS (MPS is auto-detected at runtime), Raspberry Pi, or plain CPU:
    # the standard PyPI torch wheel works for all three.
    return base


# ── Helpers ────────────────────────────────────────────────────────────────────

def _command_ok(cmd: list[str]) -> bool:
    """Return True if cmd exits with code 0 within 5 seconds."""
    try:
        result = subprocess.run(
            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


def _torch_already_installed() -> bool:
    """Return True if torch is already importable in the current environment."""
    return _command_ok([sys.executable, '-c', 'import torch'])


def run(cmd: list[str], dry_run: bool = False) -> None:
    print('  $', ' '.join(cmd))
    if not dry_run:
        subprocess.check_call(cmd)


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--dry-run', action='store_true',
                        help='Print commands without executing them')
    parser.add_argument('--list', action='store_true',
                        help='Print detected platform and exit')
    args = parser.parse_args()

    pid = detect_platform()
    print(f'\nDetected platform: {PLATFORM_LABELS[pid]}')

    if args.list:
        return

    pip = [sys.executable, '-m', 'pip', 'install']

    # ── Step 1: PyTorch ────────────────────────────────────────────────────────
    print('\n[1/2] PyTorch')
    if pid == 'jetson' and _torch_already_installed():
        print('  torch already present — skipping')
    else:
        run(pip + torch_install_args(pid), args.dry_run)

    # ── Step 2: Remaining dependencies ────────────────────────────────────────
    print('\n[2/2] Remaining dependencies (requirements.txt)')
    req = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'requirements.txt')
    run(pip + ['-r', req], args.dry_run)

    print('\nInstallation complete.')
    print('To start the server:')
    print('  uvicorn backend.main:app --host 0.0.0.0 --port 9090 --reload\n')


if __name__ == '__main__':
    main()
