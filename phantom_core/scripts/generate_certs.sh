#!/usr/bin/env bash
# Generate a self-signed TLS certificate for development / testing.
# Usage: ./scripts/generate_certs.sh [output_dir]
set -euo pipefail

CERT_DIR="${1:-certs}"
mkdir -p "$CERT_DIR"

openssl req -x509 -newkey rsa:2048 -nodes \
    -keyout "$CERT_DIR/key.pem" \
    -out    "$CERT_DIR/cert.pem" \
    -days   365 \
    -subj   "/CN=phantom-controller/O=Phantom/C=US"

chmod 600 "$CERT_DIR/key.pem"
chmod 644 "$CERT_DIR/cert.pem"

echo "✅ TLS certificate generated in $CERT_DIR/"
echo "   cert: $CERT_DIR/cert.pem"
echo "   key:  $CERT_DIR/key.pem"
