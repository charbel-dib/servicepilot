from fastapi import FastAPI, HTTPException

STATUSES = {
    "atlas": {
        "status": "degraded",
        "message": "Latence de connexion élevée ; investigation en cours.",
    },
    "nova": {"status": "operational", "message": "Aucun incident en cours."},
    "orion": {"status": "outage", "message": "Maintenance de l'espace finance."},
    "vpn": {"status": "operational", "message": "Passerelle VPN disponible."},
}

app = FastAPI(title="ServicePilot fixture status API", version="0.1.0")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/services/{service_id}")
def service_status(service_id: str):
    if service_id not in STATUSES:
        raise HTTPException(404, "Unknown service")
    return {"service_id": service_id, **STATUSES[service_id]}
