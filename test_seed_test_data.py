import pytest
from unittest.mock import patch, MagicMock
from seed_test_data import seed_multi_db, seed_modules, simulate_activity

@patch("seed_test_data.get_redis_client")
def test_seed_multi_db(mock_get_client):
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    mock_pipe = MagicMock()
    mock_client.pipeline.return_value = mock_pipe

    seed_multi_db("localhost", 6379, "pass", False)

    # Check it iterated 3 times for DBs 0, 1, 2
    assert mock_get_client.call_count == 3
    assert mock_pipe.set.call_count == 6 # 2 strings per DB
    assert mock_pipe.hset.call_count == 6 # 2 hashes per DB
    assert mock_pipe.lpush.call_count == 3 # 1 list per DB
    assert mock_pipe.execute.call_count == 3

def test_seed_modules_json_search():
    mock_client = MagicMock()
    # Mock MODULE LIST output [name, rejson, ver, 1] and [name, search, ver, 1]
    mock_client.execute_command.side_effect = [
        [["name", "rejson", "ver", 1], ["name", "search", "ver", 1]], # Call 1: MODULE LIST
        True, # Call 2: JSON.SET
        True  # Call 3: HSET
    ]

    seed_modules(mock_client)

    # Should call execute_command for MODULE LIST and JSON.SET
    assert mock_client.execute_command.call_count == 2
    # Check HSET was called for RediSearch
    assert mock_client.hset.call_count == 1

    # Verify the JSON.SET args
    args, _ = mock_client.execute_command.call_args_list[1]
    assert args[0] == "JSON.SET"
    assert args[1] == "product:1"

@patch("time.time")
@patch("time.sleep")
def test_simulate_activity(mock_sleep, mock_time):
    # Control the while loop to run exactly 2 times
    mock_time.side_effect = [0, 1, 3, 11] # start=0, diff=1 (<10), diff=3 (<10), diff=11 (>10)

    mock_client = MagicMock()
    mock_pipe = MagicMock()
    mock_client.pipeline.return_value = mock_pipe

    simulate_activity(mock_client, duration=10)

    assert mock_pipe.set.call_count == 2
    assert mock_pipe.get.call_count == 2
    assert mock_pipe.delete.call_count == 2
    assert mock_pipe.execute.call_count == 2
