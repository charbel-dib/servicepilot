"""A second SDK consumer, using a separate corpus and no HTTP calls."""

import tempfile
from pathlib import Path

from servicepilot import Principal, ServicePilot
from servicepilot.config import Settings

with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    corpus = root / "procedures"
    corpus.mkdir()
    (corpus / "nova-welcome.md").write_text(
        "service: nova\n# Bien démarrer avec Nova\n\n"
        "Pour votre arrivée, retrouvez le guide d'accueil Nova dans l'espace documentaire. "
        "Votre responsable valide les droits d'accès. Ne partagez jamais votre mot de passe.\n",
        encoding="utf-8",
    )
    settings = Settings(
        provider="offline",
        data_dir=root / "state",
        procedures_dir=corpus,
        embedding_backend="hashing",
        _env_file=None,
    )
    with ServicePilot(settings) as pilot:
        user = Principal(user_id="newcomer", services=frozenset({"nova"}))
        result = pilot.run("Quel guide pour mon arrivée et démarrer avec Nova ?", user)
        assert result.status == "complete"
        assert [event.tool for event in result.trace] == ["search_procedures"]
        print(result.model_dump_json(indent=2))
