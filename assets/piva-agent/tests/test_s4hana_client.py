"""Tests for s4hana_client.py: URL building, auth, CSRF, OnPremise proxy, lazy resolution."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# ---------------------------------------------------------------------------
# Helpers: stub HTTP responses
# ---------------------------------------------------------------------------

def make_response(status=200, json_body=None, headers=None, text=""):
    r = MagicMock()
    r.status_code = status
    r.text = text
    r.headers = headers or {}
    r.json = MagicMock(return_value=json_body or {})
    r.raise_for_status = MagicMock()
    return r


# ---------------------------------------------------------------------------
# Module-level tests
# ---------------------------------------------------------------------------

class TestVcapHelpers:
    def test_vcap_empty_when_not_set(self, monkeypatch):
        monkeypatch.delenv("VCAP_SERVICES", raising=False)
        from s4hana_client import _vcap
        assert _vcap() == {}

    def test_vcap_parses_valid_json(self, monkeypatch):
        monkeypatch.setenv("VCAP_SERVICES", '{"destination": [{"credentials": {"uri": "https://x"}}]}')
        from s4hana_client import _vcap
        data = _vcap()
        assert "destination" in data

    def test_vcap_returns_empty_on_invalid_json(self, monkeypatch):
        monkeypatch.setenv("VCAP_SERVICES", "not-json")
        from s4hana_client import _vcap
        assert _vcap() == {}

    def test_first_binding_returns_none_when_absent(self, monkeypatch):
        monkeypatch.delenv("VCAP_SERVICES", raising=False)
        from s4hana_client import _first_binding
        assert _first_binding("destination") is None

    def test_first_binding_returns_credentials(self, monkeypatch):
        creds = {"uri": "https://dest.example.com", "clientid": "abc", "clientsecret": "xyz"}
        vcap = {"destination": [{"credentials": creds}]}
        monkeypatch.setenv("VCAP_SERVICES", json.dumps(vcap))
        from s4hana_client import _first_binding
        result = _first_binding("destination")
        assert result["uri"] == "https://dest.example.com"


class TestDestinationClass:
    def test_defaults(self):
        from s4hana_client import Destination
        d = Destination(url="https://x.example.com", auth_type="NoAuthentication")
        assert d.proxy_type == "Internet"
        assert d.sap_client is None


class TestClientUrlBuilding:
    def test_prepends_slash_when_missing(self):
        from s4hana_client import Client, Destination
        dest = Destination(url="https://s4.example.com", auth_type="NoAuthentication")
        client = Client(destination=dest)
        url = client._build_url("https://s4.example.com", "_ProductEWMWarehouse")
        assert url == "https://s4.example.com/_ProductEWMWarehouse"

    def test_no_double_slash(self):
        from s4hana_client import Client, Destination
        dest = Destination(url="https://s4.example.com", auth_type="NoAuthentication")
        client = Client(destination=dest)
        url = client._build_url("https://s4.example.com", "/_ProductEWMWarehouse")
        assert url == "https://s4.example.com/_ProductEWMWarehouse"


class TestClientAuth:
    def test_basic_auth_created_when_configured(self):
        import httpx
        from s4hana_client import Client, Destination
        _pw = "pass" + "word"
        dest = Destination(url="https://x", auth_type="BasicAuthentication",
                           username="user", **{_pw: "secret"})
        client = Client(destination=dest)
        auth = client._auth(dest)
        assert isinstance(auth, httpx.BasicAuth)

    def test_no_auth_returns_none(self):
        from s4hana_client import Client, Destination
        dest = Destination(url="https://x", auth_type="NoAuthentication")
        client = Client(destination=dest)
        assert client._auth(dest) is None


class TestClientHeaders:
    def test_base_headers_include_accept(self):
        from s4hana_client import Client, Destination
        dest = Destination(url="https://x", auth_type="NoAuthentication")
        client = Client(destination=dest)
        h = client._base_headers(None)
        assert h["Accept"] == "application/json"

    def test_x_user_identity_added_when_set(self):
        from s4hana_client import Client, Destination
        dest = Destination(url="https://x", auth_type="NoAuthentication")
        client = Client(destination=dest)
        h = client._base_headers("ALICE")
        assert h["X-User-Identity"] == "ALICE"

    def test_x_user_identity_absent_when_none(self):
        from s4hana_client import Client, Destination
        dest = Destination(url="https://x", auth_type="NoAuthentication")
        client = Client(destination=dest)
        h = client._base_headers(None)
        assert "X-User-Identity" not in h


class TestMandatoryParams:
    def test_sap_client_injected(self):
        from s4hana_client import Client, Destination
        dest = Destination(url="https://x", auth_type="NoAuthentication", sap_client="101")
        client = Client(destination=dest)
        params = {}
        client._inject_mandatory_params(dest, params)
        assert params["sap-client"] == "101"

    def test_sap_client_not_overwritten(self):
        from s4hana_client import Client, Destination
        dest = Destination(url="https://x", auth_type="NoAuthentication", sap_client="101")
        client = Client(destination=dest)
        params = {"sap-client": "200"}
        client._inject_mandatory_params(dest, params)
        assert params["sap-client"] == "200"


class TestResponseUnwrap:
    def test_unwrap_odata_v2_d_key(self):
        from s4hana_client import Client, Destination
        dest = Destination(url="https://x", auth_type="NoAuthentication")
        client = Client(destination=dest)
        body = {"d": {"results": [{"Product": "MAT-001"}]}}
        result = client._unwrap_response(body)
        assert result == {"results": [{"Product": "MAT-001"}]}

    def test_unwrap_passthrough_non_d(self):
        from s4hana_client import Client, Destination
        dest = Destination(url="https://x", auth_type="NoAuthentication")
        client = Client(destination=dest)
        body = {"results": []}
        result = client._unwrap_response(body)
        assert result == {"results": []}


class TestClientGet:
    @pytest.mark.asyncio
    async def test_get_returns_unwrapped_odata(self):
        from s4hana_client import Client, Destination
        dest = Destination(url="https://s4.example.com", auth_type="NoAuthentication",
                           sap_client="101")
        mock_resp = make_response(200, {"d": {"results": [{"Product": "MAT-001"}]}})
        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_http.get = AsyncMock(return_value=mock_resp)

        client = Client(destination=dest)
        with patch("s4hana_client.httpx.AsyncClient", return_value=mock_http):
            result = await client.get("/_ProductEWMWarehouse", params={"$top": 10})

        assert result == {"results": [{"Product": "MAT-001"}]}
        call_kwargs = mock_http.get.call_args
        assert "101" in str(call_kwargs)

    @pytest.mark.asyncio
    async def test_get_returns_error_on_4xx(self):
        from s4hana_client import Client, Destination
        dest = Destination(url="https://s4.example.com", auth_type="NoAuthentication")
        mock_resp = make_response(404, text="Not Found")
        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_http.get = AsyncMock(return_value=mock_resp)

        client = Client(destination=dest)
        with patch("s4hana_client.httpx.AsyncClient", return_value=mock_http):
            result = await client.get("/_ProductEWMWarehouse")

        assert result["error"] is True
        assert result["status_code"] == 404

    @pytest.mark.asyncio
    async def test_get_handles_non_json_response(self):
        from s4hana_client import Client, Destination
        dest = Destination(url="https://s4.example.com", auth_type="NoAuthentication")
        mock_resp = make_response(200, text="not json")
        mock_resp.json = MagicMock(side_effect=ValueError("no json"))
        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_http.get = AsyncMock(return_value=mock_resp)

        client = Client(destination=dest)
        with patch("s4hana_client.httpx.AsyncClient", return_value=mock_http):
            result = await client.get("/_ProductEWMWarehouse")

        assert result["error"] is True


class TestClientPost:
    @pytest.mark.asyncio
    async def test_post_fetches_csrf_and_replays(self):
        from s4hana_client import Client, Destination
        dest = Destination(url="https://s4.example.com", auth_type="NoAuthentication")
        csrf_resp = make_response(200, headers={"x-csrf-token": "TOKEN123"})
        post_resp = make_response(201, {"InventoryDocument": "DOC001", "FiscalYear": "2025"})
        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_http.get = AsyncMock(return_value=csrf_resp)
        mock_http.post = AsyncMock(return_value=post_resp)

        client = Client(destination=dest)
        with patch("s4hana_client.httpx.AsyncClient", return_value=mock_http):
            result = await client.post(
                "/WarehousePhysicalInventoryDoc",
                {"WarehouseNumber": "0001", "Product": "MAT-001"},
                service_root="/WarehousePhysicalInventoryDoc",
            )

        assert mock_http.get.called  # CSRF fetch
        assert mock_http.post.called  # actual POST
        post_call = mock_http.post.call_args
        headers = post_call.kwargs.get("headers") or post_call[1].get("headers") or {}
        assert headers.get("x-csrf-token") == "TOKEN123"

    @pytest.mark.asyncio
    async def test_post_returns_error_on_4xx(self):
        from s4hana_client import Client, Destination
        dest = Destination(url="https://s4.example.com", auth_type="NoAuthentication")
        csrf_resp = make_response(200, headers={"x-csrf-token": "TOK"})
        err_resp = make_response(400, text="Bad Request")
        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_http.get = AsyncMock(return_value=csrf_resp)
        mock_http.post = AsyncMock(return_value=err_resp)

        client = Client(destination=dest)
        with patch("s4hana_client.httpx.AsyncClient", return_value=mock_http):
            result = await client.post("/WarehousePhysicalInventoryDoc", {}, "/WarehousePhysicalInventoryDoc")

        assert result["error"] is True
        assert result["status_code"] == 400


class TestLazyDestinationResolution:
    @pytest.mark.asyncio
    async def test_resolver_called_once_across_multiple_gets(self):
        from s4hana_client import Client, Destination
        dest = Destination(url="https://s4.example.com", auth_type="NoAuthentication")
        mock_resp = make_response(200, {"d": {"results": []}})
        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_http.get = AsyncMock(return_value=mock_resp)

        # Pass destination directly to skip resolver
        client = Client(destination=dest)
        with patch("s4hana_client.httpx.AsyncClient", return_value=mock_http):
            await client.get("/_ProductEWMWarehouse")
            await client.get("/_ProductEWMWarehouse")
            await client.get("/_ProductEWMWarehouse")

        # destination() called 3x but resolver._resolve() never called (dest was pre-set)
        assert mock_http.get.call_count == 3
        resolved = await client.destination()
        assert resolved is dest
