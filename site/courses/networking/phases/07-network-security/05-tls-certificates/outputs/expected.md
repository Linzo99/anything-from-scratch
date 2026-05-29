# Expected Output

Running `bash cert_inspector.sh` should produce:

```
TLS Certificate Inspector Demo
Working directory: /tmp/tmp.XXXXXXXX

>>> Step 1: Generate a self-signed Root CA certificate
$ openssl genrsa -out '/tmp/tmp.XXXXXXXX/ca.key' 2048
$ openssl req -new -x509 -key ... -subj '/C=US/ST=California/O=Demo CA/CN=Demo Root CA' ...

CA certificate generated:
subject=C=US, ST=California, O=Demo CA, CN=Demo Root CA
issuer=C=US, ST=California, O=Demo CA, CN=Demo Root CA
notBefore=May 29 12:00:00 2026 GMT
notAfter=May 27 12:00:00 2036 GMT

>>> Step 2: Generate server private key and CSR
...

>>> Step 3: CA signs the server certificate
Certificate request self-signature ok
subject=C=US, ST=California, L=San Francisco, O=Demo Corp, CN=demo.example.com

>>> Step 4: Inspect ALL fields of the server certificate
Certificate:
    Data:
        Version: 3 (0x2)
        Serial Number: ...
        Signature Algorithm: sha256WithRSAEncryption
        Issuer: C=US, ST=California, O=Demo CA, CN=Demo Root CA
        Validity
            Not Before: May 29 12:00:00 2026 GMT
            Not After : May 29 12:00:00 2027 GMT
        Subject: C=US, ST=California, L=San Francisco, O=Demo Corp, CN=demo.example.com
        ...
        X509v3 Subject Alternative Name:
            DNS:demo.example.com, DNS:www.demo.example.com, DNS:api.demo.example.com, IP Address:127.0.0.1
        X509v3 Key Usage:
            Key Encipherment, Data Encipherment, Digital Signature
        X509v3 Extended Key Usage:
            TLS Web Server Authentication

>>> Step 5: Verify the certificate chain
/tmp/.../server.crt: OK

>>> Step 6: What a browser would see
──────────────────────────────────────────────────────────
  Subject: C=US, ST=California, L=San Francisco, O=Demo Corp, CN=demo.example.com
  Issuer:  C=US, ST=California, O=Demo CA, CN=Demo Root CA
  Validity:
    Not Before: May 29 12:00:00 2026 GMT
    Not After:  May 29 12:00:00 2027 GMT
  Subject Alternative Names:
    DNS:demo.example.com, DNS:www.demo.example.com, DNS:api.demo.example.com, IP:127.0.0.1
  Key Usage: Key Encipherment, Data Encipherment, Digital Signature
  Extended Key Usage: TLS Web Server Authentication
  SHA-256 Fingerprint: AB:CD:EF:...

>>> Step 7: Show what happens with a self-signed cert (not trusted by OS)
  server.crt: ... unable to get local issuer certificate
  => 'unable to get local issuer certificate' = browser would show UNTRUSTED warning

  /tmp/.../server.crt: OK
  => 'OK' = chain is valid when the CA is trusted
```

## Common issues

- **Issue**: `openssl: command not found` — **Fix**: Install OpenSSL with `sudo apt install openssl`. On macOS: `brew install openssl`.
- **Issue**: Step 5 fails with "unable to get local issuer certificate" when using `-CAfile` — **Fix**: Ensure the CA cert (`ca.crt`) was generated in Step 1 and the path in `-CAfile` is correct. The script uses absolute paths from `$WORKDIR`.
