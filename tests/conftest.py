"""Shared pytest fixtures for MCP server tests."""

import pytest

from minimi_trust.mcp_server.server import build_server


@pytest.fixture
def server():
    return build_server(db_path=":memory:")