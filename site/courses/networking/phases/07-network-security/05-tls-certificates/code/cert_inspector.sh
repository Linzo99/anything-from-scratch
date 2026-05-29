#!/usr/bin/env bash
# Run: bash cert_inspector.sh
#
# TLS Certificate Inspector
# Uses openssl to:
#   1. Generate a self-signed CA certificate
#   2. Sign a server certificate with the CA
#   3. Inspect all fields with `openssl x509 -text`
#   4. Verify the certificate chain
#   5. Show what a browser would see (Subject, Issuer, SAN, validity, key usage)
#
# Requires: openssl (>= 1.1.1)
# No root needed — writes to a temp directory.

set -euo pipefail

WORKDIR=$(mktemp -d)
trap 'rm -rf "$WORKDIR"' EXIT

log()     { printf "\n\033[1;34m>>> %s\033[0m\n" "$*"; }
section() { printf "\n\033[1;32m%s\033[0m\n" "$*"; }
cmd()     { printf "\033[0;33m$ %s\033[0m\n" "$*"; eval "$*"; }

section "TLS Certificate Inspector Demo"
echo "Working directory: $WORKDIR"

# ── Step 1: Generate a self-signed CA ────────────────────────────────────────
log "Step 1: Generate a self-signed Root CA certificate"

cmd "openssl genrsa -out '$WORKDIR/ca.key' 2048 2>/dev/null"

cmd "openssl req -new -x509 \
  -key '$WORKDIR/ca.key' \
  -out '$WORKDIR/ca.crt' \
  -days 3650 \
  -subj '/C=US/ST=California/O=Demo CA/CN=Demo Root CA' \
  -extensions v3_ca"

echo ""
echo "CA certificate generated:"
openssl x509 -in "$WORKDIR/ca.crt" -noout -subject -issuer -dates

# ── Step 2: Generate a server key and CSR ────────────────────────────────────
log "Step 2: Generate server private key and Certificate Signing Request (CSR)"

cmd "openssl genrsa -out '$WORKDIR/server.key' 2048 2>/dev/null"

# Create a config file with Subject Alternative Names (SANs)
cat > "$WORKDIR/server.cnf" << 'EOF'
[req]
distinguished_name = req_distinguished_name
req_extensions     = v3_req
prompt             = no

[req_distinguished_name]
C  = US
ST = California
L  = San Francisco
O  = Demo Corp
CN = demo.example.com

[v3_req]
keyUsage         = keyEncipherment, dataEncipherment, digitalSignature
extendedKeyUsage = serverAuth
subjectAltName   = @alt_names

[alt_names]
DNS.1 = demo.example.com
DNS.2 = www.demo.example.com
DNS.3 = api.demo.example.com
IP.1  = 127.0.0.1
EOF

cmd "openssl req -new \
  -key '$WORKDIR/server.key' \
  -out '$WORKDIR/server.csr' \
  -config '$WORKDIR/server.cnf'"

echo ""
echo "CSR subject:"
openssl req -in "$WORKDIR/server.csr" -noout -subject

# ── Step 3: Sign the server cert with the CA ──────────────────────────────────
log "Step 3: CA signs the server certificate"

cat > "$WORKDIR/ext.cnf" << 'EOF'
[v3_server]
authorityKeyIdentifier = keyid,issuer
basicConstraints       = CA:FALSE
keyUsage               = keyEncipherment, dataEncipherment, digitalSignature
extendedKeyUsage       = serverAuth
subjectAltName         = @alt_names

[alt_names]
DNS.1 = demo.example.com
DNS.2 = www.demo.example.com
DNS.3 = api.demo.example.com
IP.1  = 127.0.0.1
EOF

cmd "openssl x509 -req \
  -in '$WORKDIR/server.csr' \
  -CA '$WORKDIR/ca.crt' \
  -CAkey '$WORKDIR/ca.key' \
  -CAcreateserial \
  -out '$WORKDIR/server.crt' \
  -days 365 \
  -extfile '$WORKDIR/ext.cnf' \
  -extensions v3_server"

# ── Step 4: Full certificate inspection ──────────────────────────────────────
log "Step 4: Inspect ALL fields of the server certificate"
echo ""
openssl x509 -in "$WORKDIR/server.crt" -text -noout

# ── Step 5: Verify the chain ─────────────────────────────────────────────────
log "Step 5: Verify the certificate chain"
cmd "openssl verify -CAfile '$WORKDIR/ca.crt' '$WORKDIR/server.crt'"

# ── Step 6: Browser-view summary ─────────────────────────────────────────────
log "Step 6: What a browser would see"
section "──────────────────────────────────────────────────────────"

echo ""
echo "  Subject (Who is this cert for?):"
openssl x509 -in "$WORKDIR/server.crt" -noout -subject | sed 's/^/    /'

echo ""
echo "  Issuer (Who signed this cert?):"
openssl x509 -in "$WORKDIR/server.crt" -noout -issuer | sed 's/^/    /'

echo ""
echo "  Validity dates:"
openssl x509 -in "$WORKDIR/server.crt" -noout -dates | sed 's/^/    /'

echo ""
echo "  Subject Alternative Names (hostnames this cert covers):"
openssl x509 -in "$WORKDIR/server.crt" -noout -ext subjectAltName | sed 's/^/    /'

echo ""
echo "  Key Usage:"
openssl x509 -in "$WORKDIR/server.crt" -noout -ext keyUsage | sed 's/^/    /'

echo ""
echo "  Extended Key Usage:"
openssl x509 -in "$WORKDIR/server.crt" -noout -ext extendedKeyUsage | sed 's/^/    /'

echo ""
echo "  Serial Number:"
openssl x509 -in "$WORKDIR/server.crt" -noout -serial | sed 's/^/    /'

echo ""
echo "  SHA-256 Fingerprint (used for certificate pinning):"
openssl x509 -in "$WORKDIR/server.crt" -noout -fingerprint -sha256 | sed 's/^/    /'

section "──────────────────────────────────────────────────────────"

# ── Step 7: Self-signed CA verification ──────────────────────────────────────
log "Step 7: Show what happens with a self-signed cert (not trusted by OS)"
echo ""
echo "The CA cert is self-signed — it is NOT in the system trust store."
echo "Verifying WITHOUT providing the CA file (simulates a browser without the CA):"
echo ""
openssl verify "$WORKDIR/server.crt" 2>&1 | sed 's/^/  /' || true
echo ""
echo "  => 'unable to get local issuer certificate' = browser would show UNTRUSTED warning"
echo ""
echo "Verifying WITH the CA file explicitly trusted:"
openssl verify -CAfile "$WORKDIR/ca.crt" "$WORKDIR/server.crt" | sed 's/^/  /'
echo ""
echo "  => 'OK' = chain is valid when the CA is trusted"

section ""
log "Demo complete — all files in $WORKDIR (cleaned up on exit)"
