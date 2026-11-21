"""Installed dependencies are past the versions a security advisory names,
so a re-lock that drops an override fails here, not in an audit."""

import importlib.metadata

from packaging.version import Version

# GHSA-mf5v-w3w3-f6cg is fixed in 1.45.2 (pyproject.toml: [tool.uv]).
OPENTELEMETRY_FIXED = Version("1.45.2")


def test_opentelemetry_is_at_or_past_the_advisory_fix() -> None:
    for package in ("opentelemetry-sdk", "opentelemetry-exporter-otlp-proto-http"):
        assert Version(importlib.metadata.version(package)) >= OPENTELEMETRY_FIXED, package
