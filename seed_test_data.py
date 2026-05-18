import argparse
import logging
import time
import json
import redis

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def seed_multi_db(host, port, password, ssl):
    logger.info("Seeding data across multiple logical databases...")
    for db_idx in range(3):
        client = get_redis_client(host, port, password, ssl, db=db_idx)
        if not client:
            continue

        try:
            pipe = client.pipeline()
            # Strings
            pipe.set(f"user:{db_idx}:1", "Alice")
            pipe.set(f"user:{db_idx}:2", "Bob")
            # Hashes
            pipe.hset(f"profile:{db_idx}:1", mapping={"age": 30, "city": "NY"})
            pipe.hset(f"profile:{db_idx}:2", mapping={"age": 25, "city": "LA"})
            # Lists
            pipe.lpush(f"tasks:{db_idx}:1", "task1", "task2", "task3")

            pipe.execute()
            logger.info(f"Successfully seeded DB {db_idx}")
        except redis.exceptions.RedisError as e:
            logger.error(f"Error seeding DB {db_idx}: {e}")
        finally:
            client.close()

def seed_modules(client):
    logger.info("Checking for Enterprise Modules to seed...")
    try:
        modules_info = client.execute_command("MODULE LIST")
        active_modules = []
        for mod in modules_info:
            if isinstance(mod, dict):
                mod_dict = mod
            else:
                mod_dict = {mod[i]: mod[i+1] for i in range(0, len(mod), 2)}
            active_modules.append(mod_dict.get("name", "").lower())

        if "rejson" in active_modules:
            logger.info("RedisJSON detected. Seeding JSON document...")
            doc = {"product": "Laptop", "price": 1200, "stock": 45}
            client.execute_command("JSON.SET", "product:1", "$", json.dumps(doc))

        if "search" in active_modules:
            logger.info("RediSearch detected. Ensure schemas can bind to Hashes/JSON...")
            # Often FT.CREATE is used, but requires explicit schema knowledge.
            # Storing basic indexable hashes is enough to verify module presence in stats.
            client.hset("searchable:1", mapping={"title": "Hello World", "body": "Testing search data"})

    except redis.exceptions.ResponseError as e:
        logger.warning(f"MODULE LIST not supported or failed: {e}")
    except redis.exceptions.RedisError as e:
        logger.error(f"Error checking modules: {e}")

def simulate_activity(client, duration=10):
    logger.info(f"Simulating activity pipeline for {duration} seconds...")
    start_time = time.time()
    loops = 0

    try:
        while time.time() - start_time < duration:
            pipe = client.pipeline()
            pipe.set("activity:test_key", "value")
            pipe.get("activity:test_key")
            pipe.delete("activity:test_key")
            pipe.execute()
            loops += 1
            # Slight sleep to not overload the CPU entirely
            time.sleep(0.01)

        logger.info(f"Activity simulation completed. Processed {loops * 3} commands.")
    except redis.exceptions.RedisError as e:
        logger.error(f"Error during activity simulation: {e}")

def get_redis_client(host, port, password, ssl, db=0):
    try:
        return redis.Redis(
            host=host,
            port=port,
            password=password,
            db=db,
            ssl=ssl,
            ssl_cert_reqs='none',
            decode_responses=True,
            socket_timeout=5
        )
    except Exception as e:
        logger.error(f"Failed to initialize Redis client: {e}")
        return None

def main():
    parser = argparse.ArgumentParser(description="Redis Assessment Data Seeder Tool")
    parser.add_argument("--host", required=True, help="Target Redis Host")
    parser.add_argument("--port", type=int, default=6379, help="Target Redis Port")
    parser.add_argument("--password", default=None, help="Redis Auth Password")
    parser.add_argument("--ssl", action="store_true", help="Enable SSL Connections")

    args = parser.parse_args()

    client = get_redis_client(args.host, args.port, args.password, args.ssl)
    if not client:
        return

    try:
        client.ping()
        logger.info(f"Connected successfully to {args.host}:{args.port}")

        seed_multi_db(args.host, args.port, args.password, args.ssl)
        seed_modules(client)
        simulate_activity(client, duration=10)

        logger.info("Data seeding finished successfully.")
    except redis.exceptions.ConnectionError as e:
        logger.error(f"Connection failed: {e}")
        return
    finally:
        client.close()

if __name__ == "__main__":
    main()
