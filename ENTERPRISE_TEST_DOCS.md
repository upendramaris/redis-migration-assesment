# Redis Enterprise Active-Active Testing Environment

This directory contains configuration to spin up a simulated Redis Enterprise multi-region deployment.
The simulation utilizes the official `redislabs/redis` image to stand up two nodes acting as independent clusters to test the `redis_assess.py` logic targeting Enterprise REST APIs and specific module checks.

## Environment Architecture

- **Node 1 (Cluster 1)**: `localhost`
  - Admin UI: `https://localhost:8443`
  - REST API: `https://localhost:9443`
  - Database Port: `12000`
- **Node 2 (Cluster 2)**: `localhost`
  - Admin UI: `https://localhost:8444`
  - REST API: `https://localhost:9445`
  - Database Port: `12001` (Note: Script currently stands up DB primarily on Node 1 mapped to 12000 for assessment scraping simulation).

## Startup Instructions

1. **Start the Docker Containers:**
```bash
docker compose -f docker-compose.enterprise.yml up -d
```

2. **Run the Initialization Automation:**
The containers require configuration via their REST APIs to bootstrap the clusters, set up credentials, and create a shared database with the RediSearch module loaded.

```bash
python setup-enterprise.py
```
*Note: This script will block until the containers fully initialize their APIs and sync.*

## Assessment Script Test Vectors

Once initialized, use the assessment tool against Node 1 to test full Enterprise harvesting:

**Connection String & Credentials:**
- Host: `localhost`
- API Port: `9443`
- DB Port: `12000`
- Username: `admin@example.com`
- Password: `admin123`
- SSL: `--no-ssl` (Localhost self-signed cert bypass)

**Test Command:**
```bash
python redis_assess.py --host localhost --api-port 9443 --port 12000 --username "admin@example.com" --password "admin123" --no-ssl
```

Expected output should correctly identify the `cluster1.local` topology, 2 logical shards mapping to the single node, and correctly parse the `search` module lowering the GCP migration compatibility score.