# Redis Migration Assessment & Testing Suite

## 1. Project Overview & Architecture

This repository contains a comprehensive suite of tools designed to assess, map, and document existing Redis and Redis Enterprise estates. The primary goal is to provide a seamless, shard-by-shard migration planning framework targeting Google Cloud Platform (GCP) natively.

### Core Features:
- **Automated Topology Discovery**: Identifies standalone, Sentinel, or clustered architectures using standard Redis protocols or Redis Enterprise REST APIs.
- **REST API Scraping**: Extracts logical database groupings, active enterprise modules, and node configurations seamlessly.
- **Granular Shard Mapping**: Pinpoints exact memory footprints, activity metrics, and replication roles per shard.
- **TLS Support**: Configurable toggles and certificate handling to map secure endpoints securely.
- **HTML/CSV Manifest Reporting**: Automatically calculates a "GCP Migration Compatibility Score", outputting findings into Markdown summaries and granular CSV spreadsheets for migration engineers.

---

## 2. Prerequisites

The following software is required to run the tools and testing environments:
- **Docker** and **Docker Compose**
- **Python 3.8+**
- `pip` packages: `redis`, `requests`, `pytest`

To install the Python dependencies:
```bash
pip install -r requirements.txt
```

---

## 3. Environment Setup & Deployment Commands

We provide comprehensive Docker Compose profiles to quickly stand up local simulations of various Redis architectures to validate the assessment script.

### a) Open-Source Standard Primary/Replica

Spins up a 1 Primary / 1 Replica architecture utilizing basic password authentication.

**Start the environment:**
```bash
docker-compose --profile standard up -d
```

**Testing TLS Encrypted Connections:**
If you wish to test SSL/TLS natively, generate local self-signed certificates and use the override file:
```bash
chmod +x gen-tls-certs.sh
./gen-tls-certs.sh
docker-compose -f docker-compose.yml -f docker-compose.tls.yml --profile standard up -d
```

### b) Redis Sentinel Architecture

Spins up a robust Sentinel network containing 1 Primary, 2 Replicas, and 3 Sentinel instances resolving internal failovers.

**Start the environment:**
```bash
docker-compose --profile sentinel up -d
```

### c) Native Redis Cluster

Spins up 6 barebone Redis instances configured for native clustering.

**Start the environment and run the initialization script:**
```bash
docker-compose --profile cluster up -d
chmod +x init-cluster.sh
./init-cluster.sh
```
*(The `init-cluster.sh` script bridges the internal docker network and officially binds the nodes via `redis-cli --cluster create`)*

### d) Redis Enterprise Active-Active Cluster

Simulates a Multi-Region CRDB setup using the official `redislabs/redis` images mapped across multiple REST API endpoints.

**Start the environment and bootstrap the clusters:**
```bash
docker-compose -f docker-compose.enterprise.yml up -d
python setup-enterprise.py
```
*(The `setup-enterprise.py` script automates the REST API calls to license, configure, and establish the Active-Active database with the RediSearch module loaded.)*

---

## 4. Test Data Injection (Seeding)

To validate the metric harvesting (e.g., active memory, ops/sec, logical keyspaces), use the included `seed_test_data.py` script to inject realistic pipelines into your deployed environments.

**Example 1: Seeding Standard Topology (No TLS)**
```bash
python seed_test_data.py --host localhost --port 6379 --password "redis_password"
```

**Example 2: Seeding TLS Enabled Topology**
```bash
python seed_test_data.py --host localhost --port 16379 --password "redis_password" --ssl
```

**Example 3: Seeding Redis Enterprise (Testing Modules)**
```bash
python seed_test_data.py --host localhost --port 12000
```
*(Note: The fallback database on port 12000 does not have a database-level password configured. The 'admin123' password is used for the Cluster REST API. The seeder automatically detects loaded modules like RedisJSON and RediSearch and writes module-specific data types to trigger metric reports).*

---

## 5. Running the Assessment Tool

### Single Cluster Assessment
Run the tool against a targeted endpoint. It will attempt to utilize both standard Redis protocols and Enterprise APIs (if available) to construct a topology map.

```bash
python redis_assess.py --host localhost --port 6379 --username "default" --password "redis_password" --no-ssl
```

*For Enterprise testing utilizing the REST API directly:*
```bash
python redis_assess.py --host localhost --api-port 9443 --port 12000 --username "admin@example.com" --password "admin123" --no-ssl
```

### Fleet-Wide Automated Assessment
Use the wrapper script to concurrently map multiple environments using a CSV inventory (`clusters.csv`).

**Example `clusters.csv` structure:**
```csv
host,port,username,password,ssl
localhost,6379,,redis_password,false
10.0.0.5,12000,admin@example.com,admin123,true
```

**Run the automated wrapper:**
```bash
python redis_automation_wrapper.py --inventory clusters.csv --output-dir ./migration_reports
```

---

## 6. Output Artifacts

The tool automatically formats the harvested metrics into two distinct reporting layers designed for migration planning. If running via the automation wrapper, these will be housed in timestamped directories (e.g., `assessments_YYYYMMDD_HHMMSS/`).

1. **`redis_migration_summary.md`**: An executive-level Markdown summary showcasing the overall cluster health, total calculated memory footprint in GB, engine versions, loaded enterprise modules, and an aggregated **GCP Migration Compatibility Score** highlighting potential migration blockers.
2. **`redis_shard_manifest.csv`**: A granular spreadsheet outlining every detected node and sub-shard. Columns include Cluster DNS, Node IPs, Slot Ranges, Roles (Primary/Replica), Memory Utilization per shard, Persistence types, and Ops/Second metrics.