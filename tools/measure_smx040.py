#!/usr/bin/env python3
"""Emit environment-specific SMX-040 security-boundary calibration evidence."""
from __future__ import annotations

import hashlib
import json
import platform
import statistics
import subprocess
import time

from splashmx.canonical.core import AssetId
from splashmx.security.physical import (
    DecoderResult, LinuxProcessDecoder, MediaDescriptor, PhysicalLimits,
    preflight_media, probe_linux_sandbox,
)


def decoder(source: bytes, descriptor: MediaDescriptor) -> DecoderResult:
    return DecoderResult(source[::-1], len(source), descriptor.image_pixels, descriptor.audio_frames, {})


def main() -> None:
    limits = PhysicalLimits()
    source = b"splashmx-calibration" * 256
    descriptor = MediaDescriptor(
        AssetId("asset.calibration"), "revision.calibration.1", hashlib.sha256(source).hexdigest(),
        len(source), len(source), 0, 0, "calibration", "1", {},
    )
    preflight_samples = []
    for _ in range(100):
        start = time.perf_counter_ns(); preflight_media(descriptor, limits); preflight_samples.append(time.perf_counter_ns() - start)
    status = probe_linux_sandbox()
    worker_samples = []
    worker_outcome = "release-blocked-missing-primitive"
    if status.ready:
        worker = LinuxProcessDecoder(decoder)
        for _ in range(5):
            start = time.perf_counter_ns(); worker.decode(source, descriptor); worker_samples.append(time.perf_counter_ns() - start)
        worker_outcome = "sandbox-exercised"
    try:
        openssl = subprocess.run(["openssl", "version"], check=True, capture_output=True, text=True, timeout=5).stdout.strip()
    except Exception:
        openssl = "unavailable"
    evidence = {
        "contract": "splashmx.smx040-calibration-evidence/1",
        "interpretation": "environment-specific evidence, not a universal performance SLO",
        "environment": {
            "platform": platform.platform(), "system": platform.system(), "machine": platform.machine(),
            "python": platform.python_version(), "openssl": openssl,
        },
        "limits": dict(limits.__dict__),
        "linux_sandbox": dict(status.__dict__),
        "preflight_median_ns": int(statistics.median(preflight_samples)),
        "linux_worker_outcome": worker_outcome,
        "linux_worker_median_ns": int(statistics.median(worker_samples)) if worker_samples else None,
        "samples": {"preflight": len(preflight_samples), "linux_worker": len(worker_samples)},
    }
    print(json.dumps(evidence, sort_keys=True))


if __name__ == "__main__":
    main()
