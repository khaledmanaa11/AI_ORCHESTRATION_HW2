import inspect
from unittest.mock import MagicMock, patch

from agent_arena.sdk.sdk import ArenaSDK


def test_arena_sdk_exposes_callable_start_referee() -> None:
    assert hasattr(ArenaSDK, "start_referee")
    assert callable(ArenaSDK.start_referee)

    sig = inspect.signature(ArenaSDK.start_referee)
    assert "config" in sig.parameters
    assert "brain_choice" in sig.parameters
    assert "move_timeout" in sig.parameters
    assert "show_transcript" in sig.parameters


def test_arena_sdk_exposes_callable_start_player() -> None:
    assert hasattr(ArenaSDK, "start_player")
    assert callable(ArenaSDK.start_player)

    sig = inspect.signature(ArenaSDK.start_player)
    assert "config" in sig.parameters
    assert "player_id" in sig.parameters
    assert "brain_choice" in sig.parameters
    assert "seed" in sig.parameters
    assert "host" in sig.parameters
    assert "port" in sig.parameters


@patch("agent_arena.sdk.sdk.RefereeServer")
@patch("agent_arena.sdk.sdk.build_referee_brain")
@patch("agent_arena.sdk.sdk.ShutdownCoordinator")
@patch("agent_arena.sdk.sdk.APIGatekeeper")
def test_start_referee_wiring(
    _mock_gatekeeper: MagicMock,
    mock_coordinator: MagicMock,
    mock_build_brain: MagicMock,
    mock_referee_server: MagicMock,
) -> None:
    # Set up mocks
    mock_config = MagicMock()
    mock_config.llm.gatekeeper.model_dump.return_value = {}
    mock_config.network.host = "127.0.0.1"

    mock_server_instance = mock_referee_server.return_value
    mock_server_instance.server.port = 8080
    mock_server_instance.game_thread = None
    mock_server_instance.exception = None

    ArenaSDK.start_referee(
        config=mock_config,
        brain_choice="simple",
        move_timeout=5.0,
        show_transcript=True,
    )

    # Assert correct parameters passed to referee server
    mock_referee_server.assert_called_once_with(
        mock_config,
        brain=mock_build_brain.return_value,
        coordinator=mock_coordinator.return_value,
    )
    # Check move_timeout overrides config
    assert mock_config.game.move_timeout_seconds == 5.0

    # Check start / stop called
    mock_server_instance.start.assert_called_once()
    mock_server_instance.stop.assert_called_once()


@patch("agent_arena.sdk.sdk.PlayerClient")
@patch("agent_arena.sdk.sdk.ShutdownCoordinator")
@patch("agent_arena.sdk.sdk.APIGatekeeper")
@patch("agent_arena.sdk.sdk.threading.Thread")
def test_start_player_wiring(
    mock_thread: MagicMock,
    _mock_gatekeeper: MagicMock,
    mock_coordinator: MagicMock,
    mock_player_client: MagicMock,
) -> None:
    # Set up mocks
    mock_config = MagicMock()
    mock_config.llm.gatekeeper.model_dump.return_value = {}
    mock_config.debate.match.seed = 42
    mock_config.network.host = "127.0.0.1"
    mock_config.network.port = 8080
    mock_config.network.connect_timeout_seconds = 10.0

    mock_client_instance = mock_player_client.return_value

    ArenaSDK.start_player(
        config=mock_config,
        player_id="test_player",
        brain_choice="seeded",
        seed=100,
        host="localhost",
        port=9090,
    )

    # Assert client created with correct args/kwargs
    mock_player_client.assert_called_once_with(
        player_id="test_player",
        host="localhost",
        port=9090,
        connect_timeout=10.0,
        seed=100,
        config=mock_config,
        coordinator=mock_coordinator.return_value,
    )

    # Assert thread started and coordinator wait was called
    mock_thread.assert_called_once()
    mock_coordinator.return_value.wait.assert_called_once()
    mock_client_instance.close.assert_called_once()
