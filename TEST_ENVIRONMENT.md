# Redis Assessment Test Environments

This directory contains configuration to spin up three distinct Redis topologies using Docker Compose to test the `redis_assessment.py` scripts.

## Prerequisites
Ensure Docker and Docker Compose are installed.
If testing TLS, first run the certificate generator script:
```bash
chmod +x gen-tls-certs.sh
./gen-tls-certs.sh
```

## 1. Standard Primary/Replica

Starts a basic primary (6379) and replica (6380) with password authentication.

**Start Environment:**
```bash
docker-compose --profile standard up -d
```

**Start Environment with TLS (Requires Certs):**
```bash
docker-compose -f docker-compose.yml -f docker-compose.tls.yml --profile standard up -d
```

**Assessment Script Inputs:**
- Host: `localhost`
- Port: `6379` (or `16379` for TLS)
- Password: `redis_password`
- SSL: Enabled if using TLS override, path to `--ca-cert ./tls/ca.crt`

---

## 2. Redis Sentinel Architecture

Starts 1 Primary, 2 Replicas, and 3 Sentinels on an isolated network.

**Start Environment:**
```bash
docker-compose --profile sentinel up -d
```

**Assessment Script Inputs:**
- Host: `localhost`
- Port: `6381` (Primary mapped port)
- Password: `sentinel_pass`
- SSL: Disabled

---

## 3. Native Redis Cluster

Starts 6 barebone Redis nodes configured for native clustering.

**Start Environment & Initialize:**
```bash
docker-compose --profile cluster up -d
chmod +x init-cluster.sh
./init-cluster.sh
```

**Assessment Script Inputs:**
- Host: `localhost`
- Port: `7000` (can use any port 7000-7005)
- Password: None
- SSL: Disabled
