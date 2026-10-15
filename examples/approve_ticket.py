"""Interactive approval, with a real human prompt. Requires a running status fixture."""

from servicepilot import Principal, ServicePilot

with ServicePilot() as pilot:
    user = Principal(user_id="example", services=frozenset({"atlas"}))
    run = pilot.run("Crée un ticket pour un problème de connexion Atlas", user)
    if run.status != "approval_required":
        raise SystemExit(f"No proposal: {run.status}")
    print(run.proposal.draft.model_dump_json(indent=2))
    print("Digest:", run.proposal.digest)
    approve = input("Approve this exact ticket? [y/N] ").strip().lower() == "y"
    result = pilot.decide(
        run.run_id, user, proposal_id=run.proposal.id, digest=run.proposal.digest, approve=approve
    )
    print(result.model_dump_json(indent=2))
