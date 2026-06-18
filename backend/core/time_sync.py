"""
NTP time synchronisation.

Stores a signed UTC offset applied to time.time() so accurate timestamps can
be burned into video frames without requiring NTP daemon access.

No external libraries — uses a raw UDP NTP query (RFC 5905).
"""
from __future__ import annotations
import logging
import socket
import struct
import time
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

_NTP_EPOCH = 2208988800   # delta (s) between NTP (1900) and Unix (1970) epochs

# Module-level state — written by sync(), read by track_loop
_offset:      float = 0.0   # seconds to add to time.time() → accurate UTC
_last_sync:   float = 0.0   # time.time() at last successful sync
_last_server: str   = ''

NTP_SERVERS = [
    'time.cloudflare.com',
    'time.google.com',
    'pool.ntp.org',
    'time.apple.com',
]


# ── Public read-access ─────────────────────────────────────────────────────────

def get_offset() -> float:
    """Return the stored UTC offset (0.0 if never synced)."""
    return _offset


def status() -> dict:
    return {
        'offset_sec': round(_offset, 6),
        'last_sync':  (
            datetime.fromtimestamp(_last_sync, tz=timezone.utc).isoformat()
            if _last_sync else None
        ),
        'server':  _last_server,
        'synced':  _last_sync > 0,
    }


# ── NTP query ──────────────────────────────────────────────────────────────────

def _query(server: str, timeout: float = 3.0) -> float:
    """Send one NTPv3 request; return corrected Unix UTC time."""
    packet = b'\x1b' + b'\x00' * 47   # Leap=0, Version=3, Mode=3 (client)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.settimeout(timeout)
        t_send = time.time()
        s.sendto(packet, (server, 123))
        data, _ = s.recvfrom(1024)
        t_recv = time.time()
    if len(data) < 48:
        raise ValueError(f'Short NTP response ({len(data)} bytes)')
    secs = struct.unpack('!I', data[40:44])[0]
    frac = struct.unpack('!I', data[44:48])[0]
    ntp_t = (secs - _NTP_EPOCH) + frac / 2**32
    rtt   = t_recv - t_send
    return ntp_t + rtt / 2   # apply RTT/2 correction


# ── Synchronise ────────────────────────────────────────────────────────────────

def sync(servers: Optional[list[str]] = None) -> dict:
    """
    Query NTP servers in order until one responds; store the offset.
    Returns the status dict.  Raises RuntimeError if all servers fail.
    """
    global _offset, _last_sync, _last_server
    targets   = servers or NTP_SERVERS
    last_err: Optional[Exception] = None

    for server in targets:
        try:
            t_before = time.time()
            ntp_t    = _query(server)
            t_after  = time.time()
            _offset      = ntp_t - (t_before + t_after) / 2
            _last_sync   = t_after
            _last_server = server
            logger.info('NTP sync via %s: offset = %+.4f s', server, _offset)
            return status()
        except Exception as exc:
            logger.warning('NTP %s failed: %s', server, exc)
            last_err = exc

    raise RuntimeError(f'All NTP servers failed — last: {last_err}')
