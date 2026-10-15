import hashlib
import re
import unicodedata

from servicepilot.models import Principal


class DomainError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def normalize(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", text.lower()) if unicodedata.category(c) != "Mn"
    )


def redact(text: str) -> str:
    """Best-effort minimization, deliberately not advertised as comprehensive DLP."""
    text = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[EMAIL]", text)
    text = re.sub(r"\bsk-[A-Za-z0-9_-]{10,}", "[SECRET]", text)
    text = re.sub(r"(?i)\bbearer\s+[A-Za-z0-9._-]+", "Bearer [SECRET]", text)
    return text


def content_policy(text: str) -> str | None:
    """Small transparent policy; access control is enforced separately."""
    text = normalize(text)
    if any(term in text for term in ("steal password", "voler les mots de passe", "exfiltrate")):
        return "Cette demande sort du périmètre du support autorisé."
    if re.search(r"(ignore|oublie).{0,35}(instructions|regles|previous)", text):
        return "La demande contient une instruction visant à contourner les règles du service."
    return None


def authorize(principal: Principal, service_id: str) -> None:
    if service_id not in principal.services:
        raise DomainError("Access to this service is not permitted", 403)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
