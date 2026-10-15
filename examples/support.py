"""Run a support task with the SDK. Start `servicepilot status` in another terminal."""

from servicepilot import Principal, ServicePilot

with ServicePilot() as pilot:
    user = Principal(user_id="example", services=frozenset({"atlas", "vpn"}))
    result = pilot.run("Problème de connexion Atlas", user)
    print(result.model_dump_json(indent=2))
