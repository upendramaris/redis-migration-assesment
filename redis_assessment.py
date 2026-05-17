import argparse
import json
import logging
import sys
import requests
import redis
from urllib3.exceptions import InsecureRequestWarning

# Suppress insecure request warnings if user disables SSL verification
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

class RedisEnterpriseAssessor:
    def __init__(self, host, port, username, password, ssl_enabled, ca_cert, api_port):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.ssl_enabled = ssl_enabled
        self.ca_cert = ca_cert
        self.api_port = api_port

        self.api_base_url = f"https://{self.host}:{self.api_port}/v1"
        self.api_verify = self.ca_cert if self.ca_cert else (not self.ssl_enabled)

        # Determine requests verify parameter
        if not self.ssl_enabled:
            self.api_verify = False
        elif self.ca_cert:
            self.api_verify = self.ca_cert
        else:
            self.api_verify = True

        self.assessment_data = {
            "cluster": {},
            "nodes": [],
            "databases": [],
            "metrics": {}
        }

    def _api_get(self, endpoint):
        """Helper to make API GET requests."""
        url = f"{self.api_base_url}{endpoint}"
        auth = (self.username, self.password) if self.username and self.password else None
        try:
            response = requests.get(url, auth=auth, verify=self.api_verify, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed for {url}: {e}")
            return None

    def discover_cluster_topology(self):
        """Uses the Redis Enterprise API to discover cluster and nodes."""
        logger.info("Discovering cluster topology via API...")

        # Get Cluster Info
        cluster_info = self._api_get("/cluster")
        if cluster_info:
            self.assessment_data["cluster"]["name"] = cluster_info.get("name")
            self.assessment_data["cluster"]["version"] = cluster_info.get("version")

        # Get Nodes
        nodes_info = self._api_get("/nodes")
        if nodes_info:
            for node in nodes_info:
                self.assessment_data["nodes"].append({
                    "id": node.get("uid"),
                    "ip": node.get("ip"),
                    "status": node.get("status"),
                    "role": node.get("role"),
                    "os": node.get("os_version"),
                    "cores": node.get("cores")
                })

        # Get Databases (Logical)
        dbs_info = self._api_get("/bdbs")
        if dbs_info:
            for db in dbs_info:
                db_details = {
                    "id": db.get("uid"),
                    "name": db.get("name"),
                    "port": db.get("port"),
                    "status": db.get("status"),
                    "memory_size": db.get("memory_size"),
                    "sharding": db.get("sharding"),
                    "shards_count": db.get("shards_count"),
                    "replication": db.get("replication"),
                    "modules": [mod.get("name") for mod in db.get("module_list", [])]
                }

                # Fetch Shards for this DB
                shards_info = self._api_get(f"/bdbs/{db.get('uid')}/shards")
                if shards_info:
                    db_details["shards"] = []
                    for shard in shards_info:
                        db_details["shards"].append({
                            "uid": shard.get("uid"),
                            "role": shard.get("role"),
                            "status": shard.get("status"),
                            "node_uid": shard.get("node_uid")
                        })

                self.assessment_data["databases"].append(db_details)

    def _get_redis_client(self, port):
        """Creates a redis client with appropriate SSL settings."""
        try:
            return redis.Redis(
                host=self.host,
                port=port,
                username=self.username,
                password=self.password,
                ssl=self.ssl_enabled,
                ssl_cert_reqs='required' if self.ca_cert else 'none',
                ssl_ca_certs=self.ca_cert,
                decode_responses=True,
                socket_timeout=5
            )
        except Exception as e:
            logger.error(f"Failed to create Redis client for port {port}: {e}")
            return None

    def harvest_redis_metrics(self):
        """Uses direct Redis connections to harvest detailed metrics."""
        logger.info("Harvesting direct Redis metrics...")

        # If API failed to find databases, we try the default port
        ports_to_check = [db.get("port") for db in self.assessment_data.get("databases", []) if db.get("port")]
        if not ports_to_check:
            ports_to_check = [self.port]

        for port in ports_to_check:
            client = self._get_redis_client(port)
            if not client:
                continue

            db_metrics = {"port": port}
            try:
                # Test connection
                client.ping()

                # Fetch INFO all
                info = client.info("all")

                # Server & DB info
                db_metrics["server"] = {
                    "redis_version": info.get("redis_version"),
                    "uptime_in_days": info.get("uptime_in_days"),
                    "os": info.get("os"),
                    "arch_bits": info.get("arch_bits"),
                    "executable": info.get("executable"),
                    "cluster_enabled": info.get("cluster_enabled", 0)
                }

                # Memory metrics
                db_metrics["memory"] = {
                    "used_memory_human": info.get("used_memory_human"),
                    "used_memory_peak_human": info.get("used_memory_peak_human"),
                    "mem_fragmentation_ratio": info.get("mem_fragmentation_ratio"),
                    "maxmemory_human": info.get("maxmemory_human"),
                    "maxmemory_policy": info.get("maxmemory_policy")
                }

                # Activity & Performance
                db_metrics["stats"] = {
                    "connected_clients": info.get("connected_clients"),
                    "instantaneous_ops_per_sec": info.get("instantaneous_ops_per_sec"),
                    "total_connections_received": info.get("total_connections_received"),
                    "total_commands_processed": info.get("total_commands_processed"),
                    "keyspace_hits": info.get("keyspace_hits"),
                    "keyspace_misses": info.get("keyspace_misses")
                }

                # Calculate hit ratio
                hits = int(info.get("keyspace_hits", 0))
                misses = int(info.get("keyspace_misses", 0))
                total_lookups = hits + misses
                db_metrics["stats"]["hit_ratio_percent"] = round((hits / total_lookups * 100), 2) if total_lookups > 0 else 0

                # Persistence Architecture
                db_metrics["persistence"] = {
                    "aof_enabled": info.get("aof_enabled", 0) == 1,
                    "rdb_bgsave_in_progress": info.get("rdb_bgsave_in_progress"),
                    "rdb_last_save_time": info.get("rdb_last_save_time"),
                    "aof_rewrite_in_progress": info.get("aof_rewrite_in_progress")
                }

                # Logical Databases (Keyspaces)
                keyspaces = {}
                for key, value in info.items():
                    if key.startswith("db") and key[2:].isdigit():
                        keyspaces[key] = value
                db_metrics["keyspaces"] = keyspaces

                # Enterprise Modules
                try:
                    modules = client.execute_command("MODULE LIST")
                    db_metrics["loaded_modules"] = []
                    for mod in modules:
                        # MODULE LIST returns a list of lists, [b'name', b'search', b'ver', 20000]
                        # since we have decode_responses=True, it's strings
                        mod_dict = {mod[i]: mod[i+1] for i in range(0, len(mod), 2)}
                        db_metrics["loaded_modules"].append({
                            "name": mod_dict.get("name"),
                            "version": mod_dict.get("ver")
                        })
                except redis.exceptions.ResponseError as e:
                    logger.warning(f"Could not fetch MODULE LIST on port {port}: {e}")

                self.assessment_data["metrics"][str(port)] = db_metrics

            except redis.exceptions.ConnectionError as e:
                logger.error(f"Failed to connect to Redis on port {port}: {e}")
            except redis.exceptions.AuthenticationError as e:
                logger.error(f"Authentication failed for Redis on port {port}: {e}")
            except Exception as e:
                logger.error(f"Unexpected error harvesting metrics on port {port}: {e}")
            finally:
                client.close()

    def run_assessment(self):
        logger.info(f"Starting Redis Enterprise Assessment for {self.host}")

        self.discover_cluster_topology()
        self.harvest_redis_metrics()

        logger.info("Assessment Complete.")
        return self.assessment_data

def main():
    parser = argparse.ArgumentParser(description="Redis Enterprise Database Assessment Script")

    # Connection details
    parser.add_argument("--host", help="Cluster DNS name or IP address")
    parser.add_argument("--port", type=int, default=6379, help="Redis Database Port (default: 6379)")
    parser.add_argument("--username", help="Redis username (optional)")
    parser.add_argument("--password", help="Redis password (optional)")

    # TLS/SSL configuration
    parser.add_argument("--ssl", action="store_true", help="Enable SSL/TLS for connections")
    parser.add_argument("--no-ssl", action="store_false", dest="ssl", help="Disable SSL/TLS verification")
    parser.set_defaults(ssl=True)
    parser.add_argument("--ca-cert", help="Path to CA certificate file for SSL verification")

    # Redis Enterprise API
    parser.add_argument("--api-port", type=int, default=9443, help="Redis Enterprise REST API port (default: 9443)")

    # Config file support
    parser.add_argument("--config", help="Path to a JSON configuration file (overrides other args if set)")

    args = parser.parse_args()

    if args.config:
        try:
            with open(args.config, 'r') as f:
                config_data = json.load(f)
                # Apply config values, overriding command line defaults if present in config
                for key, value in config_data.items():
                    setattr(args, key, value)
        except Exception as e:
            logger.error(f"Failed to read config file {args.config}: {e}")
            sys.exit(1)

    if not args.host:
        parser.error("the following arguments are required: --host (or must be provided in --config)")

    assessor = RedisEnterpriseAssessor(
        host=args.host,
        port=args.port,
        username=args.username,
        password=args.password,
        ssl_enabled=args.ssl,
        ca_cert=args.ca_cert,
        api_port=args.api_port
    )

    report = assessor.run_assessment()
    print(json.dumps(report, indent=4))

if __name__ == "__main__":
    main()
