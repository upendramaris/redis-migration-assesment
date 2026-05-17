import pytest
from unittest.mock import patch, MagicMock
import os
import subprocess
from redis_automation_wrapper import process_cluster, setup_output_directory, parse_inventory

def test_parse_inventory_success(tmp_path):
    inv_file = tmp_path / "test_clusters.csv"
    inv_file.write_text("host,port,ssl\ntarget1,6379,false\ntarget2,12000,true")

    clusters = parse_inventory(str(inv_file))

    assert len(clusters) == 2
    assert clusters[0]["host"] == "target1"
    assert clusters[1]["port"] == "12000"

def test_parse_inventory_missing_host(tmp_path):
    inv_file = tmp_path / "test_clusters.csv"
    inv_file.write_text("ip,port\n10.0.0.1,6379")

    with pytest.raises(SystemExit):
        parse_inventory(str(inv_file))

def test_setup_output_directory(tmp_path):
    out_dir = setup_output_directory(str(tmp_path))
    assert os.path.exists(out_dir)
    assert "assessments_" in out_dir

@patch("subprocess.run")
def test_process_cluster_success(mock_run, tmp_path):
    # Setup mock
    mock_run.return_value = MagicMock(returncode=0)

    cluster_row = {"host": "test_host", "port": "6379", "ssl": "false"}

    success, host, msg = process_cluster(cluster_row, str(tmp_path))

    assert success is True
    assert host == "test_host"
    assert msg == "Success"

    cluster_dir = tmp_path / "test_host"
    assert cluster_dir.exists()
    assert (cluster_dir / "test_host_config.json").exists()

@patch("subprocess.run")
def test_process_cluster_failure(mock_run, tmp_path):
    # Setup mock to fail
    mock_run.side_effect = subprocess.CalledProcessError(
        returncode=1, cmd="cmd", output="Error Out", stderr="Error Err"
    )

    cluster_row = {"host": "test_host_fail"}

    success, host, msg = process_cluster(cluster_row, str(tmp_path))

    assert success is False
    assert host == "test_host_fail"

    error_log = tmp_path / "test_host_fail" / "error.log"
    assert error_log.exists()
    assert "Error Err" in error_log.read_text()
