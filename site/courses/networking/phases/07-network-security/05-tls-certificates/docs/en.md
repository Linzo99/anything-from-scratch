# Understand TLS Certificate Validation

> Your browser trusts hundreds of certificate authorities you have never heard of — let's write the validation logic ourselves and see exactly what it checks.

**Type:** Learn
**Languages:** Python
**Prerequisites:** Phase 5, Lesson 05 — TLS Handshake and Certificates
**Time:** ~35 minutes

## Learning Objectives
- Describe the chain of trust from a leaf certificate to a root CA
- Write a Python script that connects to a TLS server and validates its certificate
- Detect and report expired, self-signed, and hostname-mismatch errors separately
- Extract and display key certificate fields: subject, issuer, SANs, validity dates
- Explain why certificate pinning exists and what it solves

## The Problem

When you navigate to `https://your-bank.com`, your browser checks the server's TLS certificate before showing you the page. This check answers: "Can I trust that this server is genuinely operated by your-bank.com, and not by an attacker who intercepted my connection?"

Most developers delegate this entirely to the browser and never think about it. But TLS certificate validation fails in predictable ways, and understanding those failure modes matters when:
- You write a Python script that fetches data from HTTPS APIs
- You build a service that verifies client certificates
- You deploy an internal service with a self-signed cert
- You want to know why your service fails HTTPS validation in CI

## The Concept

### The Certificate Chain of Trust

A TLS certificate is a document that says: "This public key belongs to the domain example.com, and I, DigiCert, vouch for this." But why should you trust DigiCert? Because a Root CA (like DigiCert Global Root CA) signed DigiCert's certificate, and your OS/browser ships with that root CA pre-installed as trusted.

```
Root CA (pre-installed in OS/browser trust store)
  └── signs ──► Intermediate CA certificate
                    └── signs ──► Leaf certificate (example.com)
```

A "chain of trust" is validated by:
1. The leaf cert is signed by the intermediate CA's key — verify signature
2. The intermediate cert is signed by the root CA's key — verify signature
3. The root CA is in our trust store — we trust it by configuration

If any link in the chain is broken (expired, wrong signature, unknown issuer), validation fails.

### Common Failure Modes

**Expired certificate**: Every certificate has `notBefore` and `notAfter` dates. If `notAfter` is in the past, the cert is expired. This is the most common real-world failure — someone forgot to renew.

**Self-signed certificate**: A cert where the issuer is the same as the subject, and is not in the OS trust store. Common in development and internal tools. Browsers show a scary warning.

**Hostname mismatch**: The certificate's Subject Alternative Names (SANs) must include the hostname you connected to. If you connect to `api.example.com` but the cert only has `example.com`, this fails. Wildcard certs (`*.example.com`) cover one level of subdomain.

**Untrusted root**: The root CA that signed the chain is not in your system's trust store. Common when an internal CA issues certs for corporate services.

**Revoked certificate**: A cert that was issued but later marked invalid (because the private key was stolen). Checked via OCSP (Online Certificate Status Protocol) or CRL (Certificate Revocation List). Python's `ssl` module does not check revocation by default.

### Python's ssl Module

Python's `ssl` module wraps OpenSSL. When you create an SSL context and connect, it performs full certificate validation by default:

```python
import ssl, socket

ctx = ssl.create_default_context()   # uses system trust store, validates by default
conn = ctx.wrap_socket(
    socket.socket(),
    server_hostname="example.com"    # used for hostname check
)
conn.connect(("example.com", 443))
cert = conn.getpeercert()            # returns parsed certificate dict
```

The `getpeercert()` method returns the validated certificate as a Python dict. If validation fails, `wrap_socket` raises `ssl.SSLCertVerificationError`.

## Build It

Save as `check_tls.py`:

```python
#!/usr/bin/env python3
"""
TLS Certificate Validator
Connects to a host:port, validates the certificate chain, and reports the result.

Usage:
  python3 check_tls.py example.com
  python3 check_tls.py example.com 8443
  python3 check_tls.py expired.badssl.com
  python3 check_tls.py self-signed.badssl.com
  python3 check_tls.py wrong.host.badssl.com
"""
import sys
import ssl
import socket
import datetime
from typing import Optional


def format_dn(rdn_sequence) -> str:
    """
    Convert the tuple-of-tuples Distinguished Name format into a readable string.
    Input: ((('countryName', 'US'),), (('organizationName', 'Example'),), ...)
    Output: "countryName=US, organizationName=Example"
    """
    parts = []
    for rdn in rdn_sequence:
        for attr_type, attr_value in rdn:
            parts.append(f"{attr_type}={attr_value}")
    return ", ".join(parts)


def check_tls_certificate(hostname: str, port: int = 443) -> dict:
    """
    Attempt to connect to hostname:port with TLS and validate the certificate.
    Returns a result dict with keys: valid, error_type, error_msg, cert_info.
    """
    result = {
        "hostname":   hostname,
        "port":       port,
        "valid":      False,
        "error_type": None,
        "error_msg":  None,
        "cert_info":  None,
    }

    # ── Attempt 1: Full validation (default) ─────────────────────────────
    ctx = ssl.create_default_context()
    try:
        with socket.create_connection((hostname, port), timeout=10) as raw_sock:
            with ctx.wrap_socket(raw_sock, server_hostname=hostname) as tls_sock:
                cert = tls_sock.getpeercert()
                result["valid"]     = True
                result["cert_info"] = _parse_cert(cert, hostname)
                return result

    except ssl.SSLCertVerificationError as e:
        # Validation failed — diagnose the specific reason
        error_str = str(e).lower()
        result["error_msg"] = str(e)

        if "expired" in error_str or "certificate has expired" in error_str:
            result["error_type"] = "EXPIRED"
        elif "self-signed" in error_str or "self signed" in error_str:
            result["error_type"] = "SELF_SIGNED"
        elif "hostname" in error_str or "does not match" in error_str:
            result["error_type"] = "HOSTNAME_MISMATCH"
        elif "unable to get local issuer" in error_str or "unknown ca" in error_str:
            result["error_type"] = "UNTRUSTED_CA"
        else:
            result["error_type"] = "CERT_ERROR"

        # ── Attempt 2: Connect without validation to extract cert info anyway
        no_verify_ctx = ssl.create_default_context()
        no_verify_ctx.check_hostname = False
        no_verify_ctx.verify_mode    = ssl.CERT_NONE
        try:
            with socket.create_connection((hostname, port), timeout=10) as raw_sock:
                with no_verify_ctx.wrap_socket(raw_sock, server_hostname=hostname) as tls_sock:
                    # getpeercert() with binary_form=True always works
                    # but returns DER bytes; we need to parse manually.
                    # Using getpeercert() without binary_form requires that
                    # CERT_NONE is set differently — use cert_reqs parameter.
                    pass
        except Exception:
            pass

        return result

    except ssl.SSLError as e:
        result["error_type"] = "SSL_ERROR"
        result["error_msg"]  = str(e)
        return result

    except (socket.timeout, ConnectionRefusedError, OSError) as e:
        result["error_type"] = "CONNECTION_ERROR"
        result["error_msg"]  = str(e)
        return result


def _parse_cert(cert: dict, hostname: str) -> dict:
    """Extract the most important fields from a getpeercert() dict."""
    info = {}

    # Subject (the entity the cert was issued to)
    info["subject"] = format_dn(cert.get("subject", ()))

    # Issuer (who signed this cert)
    info["issuer"] = format_dn(cert.get("issuer", ()))

    # Validity window
    not_before_str = cert.get("notBefore", "")
    not_after_str  = cert.get("notAfter",  "")

    fmt = "%b %d %H:%M:%S %Y %Z"
    try:
        info["not_before"] = datetime.datetime.strptime(not_before_str, fmt)
        info["not_after"]  = datetime.datetime.strptime(not_after_str,  fmt)
        now                = datetime.datetime.utcnow()
        info["days_until_expiry"] = (info["not_after"] - now).days
    except ValueError:
        info["not_before"]        = not_before_str
        info["not_after"]         = not_after_str
        info["days_until_expiry"] = None

    # Subject Alternative Names (the hostnames this cert covers)
    sans = cert.get("subjectAltName", ())
    info["san_dns"] = [value for dtype, value in sans if dtype == "DNS"]

    # Check if our hostname is covered by a SAN
    info["hostname_covered"] = _hostname_in_sans(hostname, info["san_dns"])

    # Serial number and version
    info["serial"]  = cert.get("serialNumber", "unknown")
    info["version"] = cert.get("version", "unknown")

    return info


def _hostname_in_sans(hostname: str, sans: list) -> bool:
    """Check if hostname matches any SAN (including wildcards)."""
    hostname = hostname.lower()
    for san in sans:
        san = san.lower()
        if san == hostname:
            return True
        if san.startswith("*."):
            # Wildcard: *.example.com matches foo.example.com but not example.com
            wildcard_domain = san[2:]
            parts = hostname.split(".", 1)
            if len(parts) == 2 and parts[1] == wildcard_domain:
                return True
    return False


def print_result(result: dict) -> None:
    """Print a human-readable report of the validation result."""
    host = f"{result['hostname']}:{result['port']}"
    print(f"\n{'='*60}")
    print(f"  TLS Certificate Check: {host}")
    print(f"{'='*60}")

    if result["valid"]:
        print(f"  Status: VALID")
    else:
        print(f"  Status: INVALID — {result['error_type']}")
        print(f"  Error:  {result['error_msg']}")

    info = result.get("cert_info")
    if info:
        print(f"\n  Subject : {info.get('subject', 'N/A')}")
        print(f"  Issuer  : {info.get('issuer',  'N/A')}")
        print(f"  Not Before: {info.get('not_before', 'N/A')}")
        print(f"  Not After : {info.get('not_after',  'N/A')}", end="")
        days = info.get("days_until_expiry")
        if days is not None:
            if days < 0:
                print(f"  ← EXPIRED {abs(days)} days ago!", end="")
            elif days < 14:
                print(f"  ← EXPIRES IN {days} DAYS — renew soon!", end="")
        print()
        sans = info.get("san_dns", [])
        print(f"  SANs    : {', '.join(sans) if sans else '(none)'}")
        covered = info.get("hostname_covered")
        if covered is not None:
            print(f"  Hostname covered: {'YES' if covered else 'NO — MISMATCH'}")
    print()


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    hostname = sys.argv[1]
    port     = int(sys.argv[2]) if len(sys.argv) > 2 else 443

    result = check_tls_certificate(hostname, port)
    print_result(result)

    # Exit code: 0 = valid, 1 = invalid
    sys.exit(0 if result["valid"] else 1)


if __name__ == "__main__":
    main()
```

### Testing Against Real-World Failure Cases

The `badssl.com` project provides intentionally broken TLS endpoints for testing:

```bash
# Valid certificate
python3 check_tls.py example.com

# Expired certificate
python3 check_tls.py expired.badssl.com

# Self-signed certificate
python3 check_tls.py self-signed.badssl.com

# Wrong hostname (cert is for wrong.host.badssl.com but host is badssl.com)
python3 check_tls.py wrong.host.badssl.com

# Untrusted root
python3 check_tls.py untrusted-root.badssl.com
```

Each should report a different error type. Observe the error type and the extracted cert info (when available).

### Checking Certificate Expiry for Monitoring

A practical use case: check a list of domains and warn if any cert expires soon:

```bash
#!/bin/bash
DOMAINS="example.com api.example.com cdn.example.com"
WARN_DAYS=14

for domain in $DOMAINS; do
  result=$(python3 check_tls.py "$domain" 2>&1)
  if echo "$result" | grep -q "INVALID\|EXPIRES IN [0-9] DAYS"; then
    echo "ACTION NEEDED: $domain"
    echo "$result"
  fi
done
```

## Exercises

1. **Check the full certificate chain**: Python's `ssl.SSLSocket.getpeercert()` with `binary_form=True` returns the DER-encoded leaf certificate. Use the `cryptography` library (`pip install cryptography`) to parse the full chain and print all three certificates (leaf, intermediate, root).

2. **Implement certificate pinning**: Add a `--pin` flag that accepts a SHA-256 fingerprint. After connecting, compute the leaf certificate's fingerprint and compare it to the pin. Alert if they differ. This is how mobile apps defend against MITM even with a valid CA-signed cert.

3. **Bulk scan from a file**: Accept a text file with one hostname per line. Scan all of them concurrently using `concurrent.futures.ThreadPoolExecutor`. Report a summary: N valid, N expired, N self-signed, etc.

4. **OCSP check**: Use Python's `urllib.request` to fetch the OCSP URL from the cert's Authority Information Access extension and check whether the cert has been revoked. The `cryptography` library can parse the OCSP response.

5. **Compare validation to openssl**: Run `openssl s_client -connect expired.badssl.com:443 -showcerts` and compare the output to what your script reports. Which fields does openssl show that your script does not?

## Key Terms

| Term | What people say | What it actually means |
|------|----------------|------------------------|
| Certificate chain | "cert chain" | The sequence from leaf cert to root CA; each cert is signed by the one above it |
| Root CA | "trusted root" | A certificate authority whose certificate is pre-installed in the OS/browser trust store |
| SAN | "Subject Alternative Name" | An X.509 extension that lists all domain names (and IPs) that a certificate covers |
| Self-signed | "self-signed cert" | A certificate signed with its own private key rather than by a CA; not trusted by default |
| Certificate pinning | "cert pinning" | Hardcoding a specific certificate fingerprint in an application; connections fail if the cert changes |
| OCSP | "revocation check" | Online Certificate Status Protocol — real-time check whether a cert has been revoked before its expiry |
| ssl.SSLCertVerificationError | "cert error" | Python exception raised when TLS certificate validation fails for any reason |
