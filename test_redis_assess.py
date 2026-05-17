import pytest
from unittest.mock import patch, MagicMock
from redis_assess import RedisEnterpriseAssessor
import requests
import redis

@pytest.fixture
def assessor():
    return RedisEnterpriseAssessor(
        host="test_host",
        port=6379,
        username="user",
        password="password",
        ssl_enabled=False,
        ca_cert=None,
        api_port=9443
    )

@patch("requests.get")
def test_discover_cluster_topology_success(mock_get, assessor):
    # Mock cluster API
    mock_cluster_response = MagicMock()
    mock_cluster_response.json.return_value = {"name": "test_cluster", "version": "1.0"}

    # Mock nodes API
    mock_nodes_response = MagicMock()
    mock_nodes_response.json.return_value = [{"uid": 1, "ip": "10.0.0.1", "status": "active"}]

    # Mock bdbs API
    mock_bdbs_response = MagicMock()
    mock_bdbs_response.json.return_value = [
        {"uid": 1, "name": "db1", "port": 12000, "status": "active", "module_list": [{"name": "search"}]}
    ]

    # Mock shards API
    mock_shards_response = MagicMock()
    mock_shards_response.json.return_value = [{"uid": 1, "role": "master", "status": "active", "node_uid": 1}]

    mock_get.side_effect = [mock_cluster_response, mock_nodes_response, mock_bdbs_response, mock_shards_response]

    assessor.discover_cluster_topology()

    assert assessor.assessment_data["cluster"]["name"] == "test_cluster"
    assert len(assessor.assessment_data["nodes"]) == 1
    assert len(assessor.assessment_data["databases"]) == 1
    assert assessor.assessment_data["databases"][0]["modules"] == ["search"]
    assert len(assessor.assessment_data["databases"][0]["shards"]) == 1


@patch("requests.get")
def test_discover_cluster_topology_failure(mock_get, assessor):
    mock_get.side_effect = requests.exceptions.ConnectionError("Connection Refused")
    assessor.discover_cluster_topology()

    assert assessor.assessment_data["cluster"] == {}
    assert len(assessor.assessment_data["nodes"]) == 0
    assert len(assessor.assessment_data["databases"]) == 0

@patch("redis.Redis")
def test_harvest_redis_metrics_success(mock_redis, assessor):
    mock_client = MagicMock()
    mock_redis.return_value = mock_client

    mock_client.info.return_value = {
        "redis_version": "6.2.0",
        "uptime_in_days": 10,
        "used_memory_human": "100M",
        "keyspace_hits": 80,
        "keyspace_misses": 20,
        "aof_enabled": 1,
        "db0": "keys=10,expires=0"
    }

    # Mock MODULE LIST output [b'name', b'search', b'ver', 100]
    mock_client.execute_command.return_value = [["name", "search", "ver", 100]]

    assessor.harvest_redis_metrics()

    metrics = assessor.assessment_data["metrics"]["6379"]
    assert metrics["server"]["redis_version"] == "6.2.0"
    assert metrics["memory"]["used_memory_human"] == "100M"
    assert metrics["stats"]["hit_ratio_percent"] == 80.0
    assert metrics["persistence"]["aof_enabled"] is True
    assert "db0" in metrics["keyspaces"]
    assert len(metrics["loaded_modules"]) == 1
    assert metrics["loaded_modules"][0]["name"] == "search"


@patch("redis.Redis")
def test_harvest_redis_metrics_connection_error(mock_redis, assessor):
    mock_client = MagicMock()
    mock_redis.return_value = mock_client

    mock_client.ping.side_effect = redis.exceptions.ConnectionError("Connection refused")

    assessor.harvest_redis_metrics()

    assert "6379" not in assessor.assessment_data["metrics"]


def test_generate_reports(assessor, tmp_path):
    # Setup dummy data
    assessor.assessment_data = {
        "cluster": {"name": "test_cluster", "version": "6.2.0"},
        "nodes": [{"id": 1, "ip": "10.0.0.1"}],
        "databases": [
            {
                "port": 12000,
                "modules": ["search", "graph"],
                "shards": [
                    {"uid": 100, "role": "master", "node_uid": 1}
                ]
            }
        ],
        "metrics": {
            "12000": {
                "memory": {"used_memory_human": "500M", "mem_fragmentation_ratio": "2.0"},
                "persistence": {"aof_enabled": True},
                "stats": {"instantaneous_ops_per_sec": 1500},
                "keyspaces": {"db0": "keys=100,expires=0"}
            }
        }
    }

    summary_path = tmp_path / "summary.md"
    manifest_path = tmp_path / "manifest.csv"

    assessor.generate_reports(summary_file=str(summary_path), manifest_file=str(manifest_path))

    # Assert Summary
    assert summary_path.exists()
    summary_content = summary_path.read_text()
    assert "Cluster Name:** test_cluster" in summary_content
    assert "Total Nodes:** 1" in summary_content
    assert "Active Modules:" in summary_content
    assert "graph" in summary_content
    assert "search" in summary_content
    assert "GCP Migration Compatibility Score: 70" in summary_content # 100 - 20 (graph) - 10 (frag)
    assert "Unsupported module detected: graph" in summary_content
    assert "High memory fragmentation ratio (2.0) on port 12000" in summary_content

    # Assert Manifest
    assert manifest_path.exists()
    manifest_content = manifest_path.read_text()
    assert "Cluster Name / DNS,Node ID & IP Address,Shard ID,Role,Slot Range,Database Port,Current Memory Utilization,Persistent Storage Type,Commands Per Second,Database Keys Count" in manifest_content
    assert "test_cluster,1 (10.0.0.1),100,master,N/A,12000,500M,AOF,1500,100" in manifest_content
