"""
TLS settings shared by every outbound HTTP client (GeM crawler, document
downloader). Some servers can't verify government portals against the CA
bundle that ships with Python's `certifi` package, while the operating
system's bundle (kept current by the OS) works — so prefer the system
bundle when one exists. `OUTBOUND_CA_BUNDLE` overrides both.
"""
import os

from app.core.config import get_settings

SYSTEM_CA_BUNDLES = (
    "/etc/ssl/certs/ca-certificates.crt",  # Debian / Ubuntu (incl. the backend Docker image)
    "/etc/pki/tls/certs/ca-bundle.crt",  # RHEL / Fedora
    "/etc/ssl/cert.pem",  # macOS / Alpine
)


def tls_verify() -> str | bool:
    """Value for httpx's `verify=`: a CA bundle path, or True for certifi."""
    configured = get_settings().outbound_ca_bundle
    if configured:
        return configured
    return next((path for path in SYSTEM_CA_BUNDLES if os.path.exists(path)), True)
