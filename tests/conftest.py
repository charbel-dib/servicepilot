import httpx
import pytest
from fastapi.testclient import TestClient

from servicepilot.api import create_app
from servicepilot.config import Settings
from servicepilot.connectors import HttpStatusConnector
from servicepilot.models import Principal
from servicepilot.sdk import ServicePilot
from servicepilot.status_api import STATUSES


@pytest.fixture
def settings(tmp_path):
    return Settings(data_dir=tmp_path, _env_file=None)


@pytest.fixture
def alice():
    return Principal(user_id="alice", services=frozenset({"atlas", "nova", "vpn"}))


@pytest.fixture
def bob():
    return Principal(user_id="bob", services=frozenset({"atlas", "nova", "orion", "vpn"}))


@pytest.fixture
def connector():
    def handler(request):
        service = request.url.path.split("/")[-1]
        return httpx.Response(200, json={"service_id": service, **STATUSES[service]})

    return HttpStatusConnector("http://status.test", transport=httpx.MockTransport(handler))


@pytest.fixture
def sdk(settings, connector):
    with ServicePilot(settings, status_connector=connector) as instance:
        yield instance


@pytest.fixture
def client(settings, sdk):
    with TestClient(create_app(settings, sdk)) as client:
        yield client


@pytest.fixture
def auth():
    return {"Authorization": "Bearer demo-alice-token"}
