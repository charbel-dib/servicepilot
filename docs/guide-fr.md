# Comprendre et utiliser ServicePilot

## Premier lancement

Depuis le dossier extrait, installer les dépendances avec `uv sync --frozen --extra dev`, puis lancer `uv run --frozen servicepilot demo`. Ouvrir http://127.0.0.1:8000.

Le mode initial est une simulation déterministe, clairement indiquée dans l'interface. Elle utilise réellement le graphe, les connecteurs, la recherche FAISS et la persistance. Le choix des outils est réalisé par des règles. Le mode OpenAI remplace cette politique par un modèle avec appels d'outils.

La recherche par défaut utilise des vecteurs lexicaux. L'option sentence-transformers fournit des embeddings sémantiques, avec téléchargement initial d'un modèle.

## Parcours à observer

1. Demander la procédure VPN : le système peut se contenter de rechercher un document.
2. Signaler un problème Atlas : comparer l'état courant avec les incidents historiques, qui ne prouvent pas la cause actuelle.
3. Demander un ticket Atlas : observer l'interruption du graphe, vérifier le contenu proposé puis approuver.
4. Refuser une autre proposition : constater l'absence de nouveau ticket.
5. Demander Orion avec Alice : observer le refus, puis comparer avec Bob.
6. Redémarrer l'application avec une proposition en attente : retrouver le diagnostic dans l'historique et reprendre la décision.

## Ordre de lecture du code

| Fichier | Question à comprendre |
|---|---|
| `models.py` | Quels contrats pour les entrées, réponses et propositions ? |
| `connectors.py` | Qui valide les arguments et les permissions ? |
| `retrieval.py` | Comment isoler les documents autorisés ? |
| `agent.py` | Où décide le modèle et où décide le logiciel ? |
| `storage.py` | Pourquoi une approbation ne peut-elle pas être inventée ? |
| `sdk.py` | Comment utiliser ces composants depuis une autre application ? |
| `api.py` | Comment relier identité HTTP et identité du SDK ? |
| `evaluation.py` | Qu'est-ce qui est mesuré, et qu'est-ce qui ne l'est pas ? |

## Expériences utiles

- Arrêter le service d'état et observer la réponse incomplète.
- Diminuer le budget d'appels et vérifier que le graphe s'arrête.
- Ajouter une procédure Nova, redémarrer et observer la recherche.
- Comparer les résultats avec embeddings sémantiques.
- Modifier une version du prompt, lancer les mêmes scénarios et inspecter les différences.
- Exécuter deux fois une décision identique et vérifier qu'un seul ticket existe.

Les tests couvrent plusieurs de ces situations sans clé API. Les résultats du mode déterministe ne permettent pas de conclure que le modèle réel résistera à toutes les injections. Les contrôles sur les actions sont donc placés dans le code et la base, indépendamment du modèle.

Le dossier public décrit les fonctionnalités, l'architecture, les démonstrations reproductibles et les limites du système.
