"""FR-7: WebSocket ConnectionManager unit tests.

Tests the in-memory connection manager for connect, disconnect,
broadcast, and connection counting.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest
from fastapi import WebSocket

from services.gateway.websocket_manager import ConnectionManager


@pytest.fixture
def manager() -> ConnectionManager:
    """Fresh ConnectionManager instance."""
    return ConnectionManager()


@pytest.fixture
def mock_websocket() -> AsyncMock:
    """Mock WebSocket connection."""
    ws = AsyncMock(spec=WebSocket)
    ws.accept = AsyncMock()
    ws.send_text = AsyncMock()
    ws.close = AsyncMock()
    return ws


@pytest.fixture
def mock_websocket_2() -> AsyncMock:
    """Second mock WebSocket connection."""
    ws = AsyncMock(spec=WebSocket)
    ws.accept = AsyncMock()
    ws.send_text = AsyncMock()
    ws.close = AsyncMock()
    return ws


class TestConnect:
    """FR-7: WebSocket connection management."""

    async def test_connect_accepts_websocket(
        self, manager: ConnectionManager, mock_websocket: AsyncMock
    ) -> None:
        await manager.connect(mock_websocket, "show-123")
        mock_websocket.accept.assert_called_once()

    async def test_connect_increments_connection_count(
        self, manager: ConnectionManager, mock_websocket: AsyncMock
    ) -> None:
        await manager.connect(mock_websocket, "show-123")
        assert manager.get_connection_count("show-123") == 1

    async def test_connect_multiple_clients_same_show(
        self,
        manager: ConnectionManager,
        mock_websocket: AsyncMock,
        mock_websocket_2: AsyncMock,
    ) -> None:
        await manager.connect(mock_websocket, "show-123")
        await manager.connect(mock_websocket_2, "show-123")
        assert manager.get_connection_count("show-123") == 2

    async def test_connect_different_shows(
        self, manager: ConnectionManager, mock_websocket: AsyncMock
    ) -> None:
        ws2 = AsyncMock(spec=WebSocket)
        ws2.accept = AsyncMock()

        await manager.connect(mock_websocket, "show-1")
        await manager.connect(ws2, "show-2")

        assert manager.get_connection_count("show-1") == 1
        assert manager.get_connection_count("show-2") == 1
        assert manager.get_connection_count() == 2


class TestDisconnect:
    """FR-7: WebSocket disconnection."""

    async def test_disconnect_removes_connection(
        self, manager: ConnectionManager, mock_websocket: AsyncMock
    ) -> None:
        await manager.connect(mock_websocket, "show-123")
        assert manager.get_connection_count("show-123") == 1

        await manager.disconnect(mock_websocket, "show-123")
        assert manager.get_connection_count("show-123") == 0

    async def test_disconnect_only_removes_target(
        self,
        manager: ConnectionManager,
        mock_websocket: AsyncMock,
        mock_websocket_2: AsyncMock,
    ) -> None:
        await manager.connect(mock_websocket, "show-123")
        await manager.connect(mock_websocket_2, "show-123")

        await manager.disconnect(mock_websocket, "show-123")
        assert manager.get_connection_count("show-123") == 1

    async def test_disconnect_cleans_up_empty_show(
        self, manager: ConnectionManager, mock_websocket: AsyncMock
    ) -> None:
        await manager.connect(mock_websocket, "show-123")
        await manager.disconnect(mock_websocket, "show-123")
        # Show should be removed from connections dict
        assert manager.get_connection_count("show-123") == 0

    async def test_disconnect_nonexistent_is_noop(
        self, manager: ConnectionManager, mock_websocket: AsyncMock
    ) -> None:
        await manager.disconnect(mock_websocket, "nonexistent")  # Should not raise


class TestBroadcast:
    """FR-7: Message broadcasting."""

    async def test_broadcast_sends_to_all_connected(
        self,
        manager: ConnectionManager,
        mock_websocket: AsyncMock,
        mock_websocket_2: AsyncMock,
    ) -> None:
        await manager.connect(mock_websocket, "show-123")
        await manager.connect(mock_websocket_2, "show-123")

        message = {"type": "seat_update", "seat_id": "A1", "status": "SOLD"}
        await manager.broadcast("show-123", message)

        payload = json.dumps(message)
        mock_websocket.send_text.assert_called_once_with(payload)
        mock_websocket_2.send_text.assert_called_once_with(payload)

    async def test_broadcast_noop_when_no_connections(
        self, manager: ConnectionManager
    ) -> None:
        await manager.broadcast("empty:show", {"type": "test"})  # Should not raise

    async def test_broadcast_prunes_dead_connections(
        self,
        manager: ConnectionManager,
        mock_websocket: AsyncMock,
        mock_websocket_2: AsyncMock,
    ) -> None:
        await manager.connect(mock_websocket, "show-123")
        await manager.connect(mock_websocket_2, "show-123")

        # First connection fails (dead)
        mock_websocket.send_text.side_effect = Exception("Connection closed")

        await manager.broadcast("show-123", {"type": "test"})

        # Dead connection should be pruned
        assert manager.get_connection_count("show-123") == 1
        mock_websocket_2.send_text.assert_called_once()


class TestConnectionCount:
    """FR-7: Connection counting."""

    async def test_get_connection_count_empty(
        self, manager: ConnectionManager
    ) -> None:
        assert manager.get_connection_count() == 0
        assert manager.get_connection_count("any:show") == 0

    async def test_get_connection_count_total(
        self, manager: ConnectionManager, mock_websocket: AsyncMock
    ) -> None:
        ws2 = AsyncMock(spec=WebSocket)
        ws2.accept = AsyncMock()

        await manager.connect(mock_websocket, "show-1")
        await manager.connect(ws2, "show-2")

        assert manager.get_connection_count() == 2

    async def test_get_connection_count_per_show(
        self,
        manager: ConnectionManager,
        mock_websocket: AsyncMock,
        mock_websocket_2: AsyncMock,
    ) -> None:
        await manager.connect(mock_websocket, "show-1")
        await manager.connect(mock_websocket_2, "show-1")

        ws3 = AsyncMock(spec=WebSocket)
        ws3.accept = AsyncMock()
        await manager.connect(ws3, "show-2")

        assert manager.get_connection_count("show-1") == 2
        assert manager.get_connection_count("show-2") == 1
