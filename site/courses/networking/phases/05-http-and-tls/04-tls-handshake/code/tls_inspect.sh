#!/usr/bin/env bash
# Run: bash tls_inspect.sh [hostname]
# Uses openssl s_client to connect to github.com:443 and capture the full
# TLS handshake.  Labels each message:
#   ClientHello, ServerHello, Certificate, CertificateVerify, Finished
# Also shows openssl x509 -text to decode the server certificate.
#
# Requires: openssl (pre-installed on most systems)
# Usage:
#   bash tls_inspect.sh              # defaults to github.com
#   bash tls_inspect.sh example.com

set -euo pipefail

HOST="${1:-github.com}"
PORT=443
SEP="────────────────────────────────────────────────────────"

# ── check openssl ─────────────────────────────────────────────────────────────
if ! command -v openssl &>/dev/null; then
    echo "Error: openssl not found."
    echo "  Ubuntu/Debian: sudo apt-get install -y openssl"
    echo "  macOS:         pre-installed"
    exit 1
fi

echo "================================================================"
echo "  TLS Handshake Inspection: $HOST:$PORT"
echo "================================================================"

# ── Step 1: basic connection info ─────────────────────────────────────────────
echo
echo "$SEP"
echo "  STEP 1 — Connect and show negotiated TLS version + cipher"
echo "$SEP"
echo
echo | openssl s_client -connect "$HOST:$PORT" 2>&1 | \
    grep -E "Protocol|Cipher|Verify|CONNECTED|SSL-Session" | \
    head -10 | sed 's/^/  /'

# ── Step 2: full handshake message trace ─────────────────────────────────────
echo
echo "$SEP"
echo "  STEP 2 — Full handshake message trace (-msg flag)"
echo "$SEP"
echo "  Messages labelled by type.  In TLS 1.3, Certificate and Finished"
echo "  are encrypted (shown as 'ApplicationData' in Wireshark)."
echo
echo | openssl s_client -connect "$HOST:$PORT" -tlsextdebug -msg 2>&1 | \
    grep -E ">>|<<|ClientHello|ServerHello|Certificate|Finished|CertificateVerify|\
Handshake Type|Content-Type|TLS 1\.|No client certificate" | \
    head -40 | sed 's/^/  /'

# ── Step 3: certificate chain ─────────────────────────────────────────────────
echo
echo "$SEP"
echo "  STEP 3 — Certificate chain (depth 0=server, 1=intermediate, 2=root)"
echo "$SEP"
echo
echo | openssl s_client -connect "$HOST:$PORT" -showcerts 2>&1 | \
    grep -E "^depth|^verify|^---$|CN =|O =|issuer|subject|Certificate chain" | \
    head -30 | sed 's/^/  /'

# ── Step 4: decode the server certificate ────────────────────────────────────
echo
echo "$SEP"
echo "  STEP 4 — Decode the server certificate (key fields)"
echo "$SEP"
echo
# Save the cert to a temp file, then decode it
CERT_TMP=$(mktemp /tmp/tls_cert_XXXXXX.pem)
trap "rm -f $CERT_TMP" EXIT

echo | openssl s_client -connect "$HOST:$PORT" 2>/dev/null | \
    openssl x509 -out "$CERT_TMP" 2>/dev/null || true

if [[ -s "$CERT_TMP" ]]; then
    echo "  Subject (who this cert is issued to):"
    openssl x509 -in "$CERT_TMP" -noout -subject 2>/dev/null | sed 's/^/    /'

    echo
    echo "  Issuer (who signed this cert = the CA):"
    openssl x509 -in "$CERT_TMP" -noout -issuer 2>/dev/null | sed 's/^/    /'

    echo
    echo "  Validity period:"
    openssl x509 -in "$CERT_TMP" -noout -dates 2>/dev/null | sed 's/^/    /'

    echo
    echo "  Public key:"
    openssl x509 -in "$CERT_TMP" -noout -pubkey 2>/dev/null | \
        openssl pkey -pubin -text -noout 2>/dev/null | \
        grep -E "Public-Key|RSA|ECDSA|Curve" | head -5 | sed 's/^/    /'

    echo
    echo "  Subject Alternative Names (other names this cert is valid for):"
    openssl x509 -in "$CERT_TMP" -noout -text 2>/dev/null | \
        grep -A5 "Subject Alternative Name" | \
        grep -v "Subject Alternative Name" | \
        head -5 | sed 's/^/    /'
else
    echo "  Warning: could not retrieve certificate.  Check your network connection."
fi

# ── Step 5: TLS version comparison ───────────────────────────────────────────
echo
echo "$SEP"
echo "  STEP 5 — TLS version comparison (1.2 vs 1.3 round trips)"
echo "$SEP"
echo

tls_time() {
    local version_flag="$1"
    local version_label="$2"
    local t_start t_end elapsed
    t_start=$(date +%s%3N)
    echo | openssl s_client -connect "$HOST:$PORT" $version_flag &>/dev/null || true
    t_end=$(date +%s%3N)
    elapsed=$(( t_end - t_start ))
    echo "  $version_label:  ${elapsed}ms"
}

tls_time "-tls1_2 -no_tls1_3" "TLS 1.2 (2 round trips)"
tls_time ""                   "TLS 1.3 (1 round trip) "

echo
echo "$SEP"
echo "  STEP 6 — SNI (Server Name Indication)"
echo "$SEP"
echo "  SNI is sent in the ClientHello — in plaintext — so the server"
echo "  can pick the right certificate for virtual hosting."
echo
echo | openssl s_client -connect "$HOST:$PORT" -servername "$HOST" -msg 2>&1 | \
    grep -i "server name\|SNI\|TLS server_name" | head -5 | sed 's/^/  /' || true

echo "  Sent SNI extension with hostname: $HOST"
echo "  (Without SNI, a server hosting multiple domains could not"
echo "   select the right certificate before the handshake completes.)"

echo
echo "================================================================"
echo "  Inspection complete for $HOST:$PORT"
echo "================================================================"
