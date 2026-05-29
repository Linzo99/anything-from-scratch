# Expected Output

Running `bash tls_inspect.sh github.com` should produce:

```
================================================================
  TLS Handshake Inspection: github.com:443
================================================================

────────────────────────────────────────────────────────
  STEP 1 — Connect and show negotiated TLS version + cipher
────────────────────────────────────────────────────────

  CONNECTED(00000003)
  Protocol  : TLSv1.3
  Cipher    : TLS_AES_128_GCM_SHA256
  Verify return code: 0 (ok)

────────────────────────────────────────────────────────
  STEP 2 — Full handshake message trace (-msg flag)
────────────────────────────────────────────────────────
  Messages labelled by type.  In TLS 1.3, Certificate and Finished
  are encrypted (shown as 'ApplicationData' in Wireshark).

  >> TLS 1.3, Handshake [length 0267], ClientHello
  << TLS 1.3, Handshake [length 0076], ServerHello
  << TLS 1.3, ChangeCipherSpec [length 0001]
  << TLS 1.3, ApplicationData [length 0e57]    ← contains EncryptedExtensions+Certificate+Finished
  >> TLS 1.3, ChangeCipherSpec [length 0001]
  >> TLS 1.3, ApplicationData [length 0035]    ← contains client Finished

────────────────────────────────────────────────────────
  STEP 3 — Certificate chain
────────────────────────────────────────────────────────

  depth=2 C = US, O = DigiCert Inc, OU = www.digicert.com, CN = DigiCert Global Root CA
  verify return:1
  depth=1 C = US, O = DigiCert Inc, CN = DigiCert TLS RSA SHA256 2020 CA1
  verify return:1
  depth=0 CN = github.com
  verify return:1

────────────────────────────────────────────────────────
  STEP 4 — Decode the server certificate
────────────────────────────────────────────────────────

  Subject (who this cert is issued to):
    subject=CN = github.com

  Issuer (who signed this cert = the CA):
    issuer=C = US, O = DigiCert Inc, CN = DigiCert TLS RSA SHA256 2020 CA1

  Validity period:
    notBefore=Feb 14 00:00:00 2024 GMT
    notAfter=Feb 13 23:59:59 2025 GMT

  Public key:
    Public-Key: (2048 bit)

  Subject Alternative Names:
    DNS:github.com, DNS:www.github.com

────────────────────────────────────────────────────────
  STEP 5 — TLS version comparison (1.2 vs 1.3 round trips)
────────────────────────────────────────────────────────

  TLS 1.2 (2 round trips):  245ms
  TLS 1.3 (1 round trip) :  178ms

────────────────────────────────────────────────────────
  STEP 6 — SNI (Server Name Indication)
────────────────────────────────────────────────────────
  Sent SNI extension with hostname: github.com
  (Without SNI, a server hosting multiple domains could not
   select the right certificate before the handshake completes.)

================================================================
  Inspection complete for github.com:443
================================================================
```

TLS 1.3 should be measurably faster (fewer round trips) than TLS 1.2. The exact times depend on your network latency to github.com.

## Common issues

- **Issue**: `connect: Connection refused` or `getaddrinfo: Name or service not known` → **Fix**: No internet access.  Test against a local server: run `python3 https_server.py` from the next lesson and change `HOST=localhost PORT=8443`.
- **Issue**: `verify error:num=18:self-signed certificate` → **Fix**: This is expected for self-signed certificates.  For public sites like github.com, all certificates are CA-signed and should verify without error.
- **Issue**: TLS 1.2 timing shows as faster than TLS 1.3 → **Fix**: Connection time varies with network conditions.  On first run, TCP connection setup (SYN/SYN-ACK/ACK) dominates and masks the handshake difference.  Run the comparison multiple times and average the results.
- **Issue**: `-tls1_2` flag not recognized on macOS → **Fix**: macOS ships an older openssl.  Try `brew install openssl` and use `/usr/local/opt/openssl/bin/openssl`.
