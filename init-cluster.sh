#!/bin/bash
set -e

echo "Waiting for Redis Cluster nodes to become accessible..."
sleep 10

# Create the cluster linking all 6 nodes on the bridged internal docker network
docker exec -it cluster-node-1 redis-cli --cluster create \
  cluster-node-1:7000 \
  cluster-node-2:7001 \
  cluster-node-3:7002 \
  cluster-node-4:7003 \
  cluster-node-5:7004 \
  cluster-node-6:7005 \
  --cluster-replicas 1 --cluster-yes

echo "Cluster formed successfully!"
