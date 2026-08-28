"""
M6 integration test — connects a REAL MCP client (fastmcp.Client) to the
server in-process and calls all four tools through the actual protocol
(tool discovery, JSON-RPC call, structured result), not by importing and
calling the Python functions directly. This is the build plan's explicit
M6 requirement.
"""

import json

import pytest
from fastmcp import Client

from minimi_trust.mcp_server.server import build_server


@pytest.fixture
def server():
    return build_server(db_path=":memory:")


def _payload(result) -> dict:
    """CallToolResult's structured .data is the primary path; falls back
    to parsing the text content block if a future fastmcp version ever
    changes when .data gets populated."""
    if result.data is not None:
        return result.data
    return json.loads(result.content[0].text)


@pytest.mark.asyncio
async def test_resolve_conflict_via_real_mcp_client(server):
    async with Client(server) as client:
        result = await client.call_tool(
            "resolve_conflict", {"subject": "office_relocation_date", "predicate": "is"}
        )
        payload = _payload(result)
        assert payload["subject"] == "office_relocation_date"
        assert "unresolved" in payload
        assert len(payload["version_history"]) == 2


@pytest.mark.asyncio
async def test_propose_correction_via_real_mcp_client(server):
    async with Client(server) as client:
        result = await client.call_tool("propose_correction", {
            "target_fact_id": "demo_fact_wifi", "proposed_object": "hunter3",
            "rationale": "password was rotated",
        })
        payload = _payload(result)
        assert payload["status"] == "pending"
        assert "proposal_id" in payload


@pytest.mark.asyncio
async def test_propose_correction_on_unknown_fact_returns_error_not_crash(server):
    async with Client(server) as client:
        result = await client.call_tool("propose_correction", {
            "target_fact_id": "does_not_exist", "proposed_object": "x", "rationale": "y",
        })
        payload = _payload(result)
        assert payload["error"] == "fact not found"


@pytest.mark.asyncio
async def test_verify_deletion_via_real_mcp_client(server):
    async with Client(server) as client:
        result = await client.call_tool("verify_deletion", {"target_fact_id": "demo_fact_salary_note"})
        payload = _payload(result)
        assert payload["verification_result"] in {"verified_deleted", "residual_risk_found"}
        assert "cascade_trace" in payload


@pytest.mark.asyncio
async def test_verify_deletion_on_unknown_fact_returns_error_not_crash(server):
    async with Client(server) as client:
        result = await client.call_tool("verify_deletion", {"target_fact_id": "does_not_exist"})
        payload = _payload(result)
        assert payload["error"] == "fact not found"


@pytest.mark.asyncio
async def test_explain_retrieval_via_real_mcp_client(server):
    async with Client(server) as client:
        result = await client.call_tool("explain_retrieval", {"query": "wifi password"})
        payload = _payload(result)
        assert payload["query"] == "wifi password"
        assert any(r["fact_id"] == "demo_fact_wifi" for r in payload["results"])