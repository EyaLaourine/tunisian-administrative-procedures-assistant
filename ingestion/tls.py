"""TLS context: certifi roots plus pinned intermediate certificates.

Some official servers (e.g. services.interieur.gov.tn) omit their intermediate certificate.
Browsers recover via AIA fetching; OpenSSL does not. We add the published intermediate from
config/certs/ instead of disabling verification.
"""

import ssl
from pathlib import Path

import certifi


def build_ssl_context(extra_ca_dir: Path | None) -> ssl.SSLContext:
    ctx = ssl.create_default_context(cafile=certifi.where())
    if extra_ca_dir and extra_ca_dir.is_dir():
        for pem in sorted(extra_ca_dir.glob("*.pem")):
            ctx.load_verify_locations(cafile=str(pem))
    return ctx
