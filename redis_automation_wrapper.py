import argparse
import csv
import logging
import sys
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import datetime

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def parse_inventory(inventory_file):
    clusters = []
    if not os.path.exists(inventory_file):
        logger.error(f"Inventory file {inventory_file} not found.")
        sys.exit(1)

    try:
        with open(inventory_file, 'r') as f:
            reader = csv.DictReader(f)
            # Ensure expected columns are present
            expected_cols = {'host'}
            if not expected_cols.issubset(set(reader.fieldnames or [])):
                 logger.error(f"Inventory file must contain at least 'host' column. Found: {reader.fieldnames}")
                 sys.exit(1)

            for row in reader:
                if row.get('host'):
                    clusters.append(row)
    except Exception as e:
        logger.error(f"Failed to parse inventory file: {e}")
        sys.exit(1)

    return clusters

def setup_output_directory(base_dir="."):
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    dir_name = os.path.join(base_dir, f"assessments_{timestamp}")
    os.makedirs(dir_name, exist_ok=True)
    return dir_name

def setup_master_logger(output_dir):
    log_file = os.path.join(output_dir, "master_execution.log")

    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    return log_file

def process_cluster(cluster_row, output_dir):
    host = cluster_row.get("host")
    logger.info(f"Starting assessment for {host}")

    cluster_dir = os.path.join(output_dir, host)
    os.makedirs(cluster_dir, exist_ok=True)

    summary_file = os.path.join(cluster_dir, f"{host}_summary.md")
    manifest_file = os.path.join(cluster_dir, f"{host}_manifest.csv")
    config_file = os.path.join(cluster_dir, f"{host}_config.json")

    # Write the config JSON for the target script
    with open(config_file, 'w') as f:
        # Convert ssl string to boolean if present
        if "ssl" in cluster_row and isinstance(cluster_row["ssl"], str):
             cluster_row["ssl"] = cluster_row["ssl"].lower() in ('true', '1', 't', 'y', 'yes')

        # Convert port to int if present
        for p in ["port", "api_port"]:
            if p in cluster_row and cluster_row[p]:
                try:
                    cluster_row[p] = int(cluster_row[p])
                except ValueError:
                    pass

        json.dump(cluster_row, f)

    script_path = os.path.join(os.path.dirname(__file__), "redis_assess.py")

    cmd = [
        sys.executable, script_path,
        "--config", config_file,
        "--summary-file", summary_file,
        "--manifest-file", manifest_file
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        logger.info(f"[SUCCESS] Assessment completed for {host}")
        return True, host, "Success"
    except subprocess.CalledProcessError as e:
        logger.error(f"[FAILED] Assessment failed for {host}. See logs for details.")
        error_log = os.path.join(cluster_dir, "error.log")
        with open(error_log, 'w') as f:
            f.write(f"STDOUT:\n{e.stdout}\n")
            f.write(f"STDERR:\n{e.stderr}\n")
        return False, host, "Failed (Check error.log)"
    except Exception as e:
        logger.error(f"[FAILED] Unexpected error for {host}: {e}")
        return False, host, str(e)


def main():
    parser = argparse.ArgumentParser(description="Batch Redis Enterprise Assessment Tool")
    parser.add_argument("--inventory", required=True, help="Path to CSV inventory file (must contain at least 'host' column)")
    parser.add_argument("--output-dir", default=".", help="Base output directory for assessment runs")

    args = parser.parse_args()

    clusters = parse_inventory(args.inventory)
    logger.info(f"Loaded {len(clusters)} clusters from inventory.")

    output_dir = setup_output_directory(args.output_dir)
    master_log = setup_master_logger(output_dir)

    logger.info(f"Created assessment directory: {output_dir}")

    success_count = 0
    failure_count = 0

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(process_cluster, cluster, output_dir): cluster for cluster in clusters}

        for future in as_completed(futures):
            success, host, msg = future.result()
            if success:
                success_count += 1
            else:
                failure_count += 1

    logger.info("="*40)
    logger.info(f"Batch execution complete. Success: {success_count}, Failed: {failure_count}")
    logger.info(f"Full details written to {master_log}")

if __name__ == "__main__":
    main()
