#!/bin/bash
set -e

# Prevent Git Bash (MSYS2) on Windows from translating '/' in OpenSSL subjects to paths
export MSYS_NO_PATHCONV=1

mkdir -p tls
cd tls

# Generate CA
openssl genrsa -out ca.key 4096
openssl req -x509 -new -nodes -sha256 -key ca.key -days 3650 -out ca.crt -subj "/CN=Redis-CA"

# Generate Server certs
openssl genrsa -out redis.key 2048
openssl req -new -key redis.key -out redis.csr -subj "/CN=standard-primary"
openssl x509 -req -in redis.csr -CA ca.crt -CAkey ca.key -CAcreateserial -out redis.crt -days 365 -sha256

chmod 644 *

echo "Self-signed certificates generated in ./tls directory."
