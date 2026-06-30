# TechCorp AI Chat — Challenge IA 7h

Déploiement de **Phi-3.5-Financial** derrière une **interface de chat web temps réel**,
avec un volet R&D de **fine-tuning LoRA** d'un modèle médical expérimental.

Le dépôt est organisé **par rôle** (INFRA, IA, DATA, CYBER, DEV WEB) pour que chaque
membre de l'équipe travaille et pousse sa partie.

---

## Équipe 5 (6 membres)

| Catégorie | Membres | Dossiers suggérés |
|---|---|---|
| **Cyber Sécurité** (×2) | LORET Esteban · MESGUEN Mateo | `cyber/` |
| **Développeurs** (×2) | SILOTIA Mathis · LEMEE Etienne | `webapp/` (DEV WEB) · `infra/` (INFRA) |
| **IA / Data** (×2) | LECHAT Noé · KERBOUL Gwendal | `ia/` (IA) · `data/` (DATA) |

> La mission définit **5 filières techniques** (INFRA, IA, DATA, CYBER, DEV WEB) ; l'équipe
> compte **6 personnes réparties en 3 catégories**. La colonne « Dossiers suggérés » est une
> **proposition** de répartition — ajustez-la selon vos préférences. Par exemple, au sein des
> Développeurs, l'un prend `webapp/` et l'autre `infra/` ; côté IA/Data, l'un prend `ia/` et
> l'autre `data/`.

---

## Prérequis

| Outil | Pour quoi | Note |
|---|---|---|
| Python 3.10+ | passerelle, scripts IA/DATA/CYBER | — |
| [Ollama](https://ollama.com/download) | moteur d'inférence (chemin recommandé) | port `11434` |
| Le fichier `.gguf` du modèle | importé dans Ollama | fourni par le hackathon |
| GPU CUDA (Colab Pro) | **uniquement** pour le fine-tuning LoRA | `bitsandbytes` requis |
| Navigateur récent | interface web | — |

Le **fine-tuning** est la seule étape qui exige un GPU. Tout le reste (déploiement,
interface, validation, audit) tourne sur un poste standard une fois le moteur lancé.

---

## Démarrage rapide (chemin recommandé : Ollama + passerelle)

```bash
# 1. INFRA — importer le modèle dans Ollama puis lancer le moteur
cd infra/ollama && ./deploy_ollama.sh          # ajuster la ligne FROM du Modelfile

# 2. INFRA — lancer la passerelle (exposée à DEV WEB sur :8080)
cd ../server && pip install -r requirements.txt && MODEL_NAME=phi3-financial ./run.sh

# 3. DEV WEB — servir l'interface
cd ../../webapp && python serve.py             # http://localhost:5173
```

Ouvrez **http://localhost:5173** et discutez avec le modèle.

---

## Architecture

```
┌─────────────────────┐   HTTP + SSE (CORS)   ┌──────────────────────────┐
│  Interface web      │ ───────────────────▶ │  Passerelle FastAPI      │
│  webapp/ (:5173)    │ ◀─────────────────── │  infra/server (:8080)    │
│  - streaming        │   data: {delta:...}   │  /health /chat /v1/...   │
│  - ticker /health   │                       └───────────┬──────────────┘
└─────────────────────┘                                   │ /api/chat (NDJSON)
                                                          ▼
                                              ┌──────────────────────────┐
                                              │  Ollama (:11434)         │
                                              │  modèle GGUF quantisé    │
                                              └───────────┬──────────────┘
                                                          ▼
                                              ┌──────────────────────────┐
                                              │  Phi-3.5-Financial        │
                                              │  (fourni, models/…)       │
                                              └──────────────────────────┘
```

**Flux d'une requête :** le front envoie tout l'historique à `/chat` → la passerelle
ajoute le prompt système et appelle Ollama en streaming → chaque token est reconverti en
évènement SSE `data: {"delta": "..."}` → à la fin, `{"done": true, "stats": {...}}`
(latence, tok/s) → le front affiche au fil de l'eau et met à jour son bandeau d'état.

**Pourquoi une passerelle plutôt qu'Ollama en direct :**
1. **CORS** géré proprement (Ollama bloque les requêtes navigateur par défaut) ;
2. **découplage** front ↔ moteur (changer de moteur sans toucher au front) ;
3. **observabilité** : mesure centralisée de la latence et du débit (utile à IA et CYBER).

Détail complet dans [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

---

## Structure du dépôt

```
techcorp-ai-chat/
├── README.md                 ← ce fichier
├── .gitignore
├── requirements.txt          ← méta (pointe vers les requirements par dossier)
├── docs/
│   └── ARCHITECTURE.md
├── infra/                    ← INFRA
│   ├── README.md
│   ├── DEPLOYMENT.md
│   ├── server/               ← passerelle FastAPI
│   │   ├── app.py
│   │   ├── requirements.txt
│   │   └── run.sh
│   ├── ollama/
│   │   ├── Modelfile
│   │   └── deploy_ollama.sh
│   └── triton/README.md      ← alternative documentée
├── ia/                       ← IA
│   ├── README.md
│   ├── validate_phi3_financial.py
│   ├── finetune_lora_medical.py
│   ├── test_medical_model.py
│   ├── inference_params.md
│   └── requirements.txt
├── data/                     ← DATA
│   ├── README.md
│   ├── prepare_medical_dataset.py
│   ├── validate_finance_inputs.py
│   └── requirements.txt
├── cyber/                    ← CYBER
│   ├── README.md
│   ├── SECURITY_AUDIT.md
│   ├── scan_inherited_files.py
│   ├── robustness_tests.py
│   ├── bias_check.py
│   └── requirements.txt
└── webapp/                   ← DEV WEB (livrable obligatoire)
    ├── README.md
    ├── index.html
    ├── styles.css
    ├── app.js
    ├── config.js
    └── serve.py
```

---

## Les 5 rôles en détail

### INFRA — l'architecte du système (`infra/`)
Déploie le moteur d'inférence et l'expose à DEV WEB. Choix retenu : **Ollama** (moteur,
quantization GGUF intégrée) + **passerelle FastAPI** devant (CORS, découplage,
observabilité). Triton et un serveur maison (vLLM / llama.cpp) sont documentés en
alternative. Endpoints de la passerelle : `/health`, `/chat` (SSE), `/v1/chat/completions`
(compatible OpenAI). Configuration via variables : `OLLAMA_BASE_URL`, `MODEL_NAME`,
`ALLOWED_ORIGINS`, `PORT`.

### IA — le spécialiste modèles (`ia/`)
1. **Valide** Phi-3.5-Financial via la passerelle → `validation_report.md` (latence,
   débit, réussite par test).
2. **Documente** les réglages d'inférence (balayage de température, voir
   `inference_params.md`).
3. **Fine-tune** un modèle médical en **QLoRA 4-bit** (`finetune_lora_medical.py`,
   Colab GPU) puis le teste. **Base par défaut** : `microsoft/Phi-3.5-mini-instruct`
   (configurable). Exercice de R&D — **pas de production, pas d'avis médical.**

### DATA — l'expert données (`data/`)
1. **Prépare et nettoie** le dataset `ruslanmv/ai-medical-chatbot` → `medical_chat.jsonl`
   (format chat) + `quality_report.md`. Nettoyage : normalisation des espaces, rejet des
   entrées vides / trop courtes / trop longues, déduplication exacte, comptage des PII
   (email / téléphone).
2. **Valide les entrées** du modèle financier (vide, très long, caractères de contrôle,
   unicode, injection basique) et transmet les cas sensibles à CYBER.

### CYBER — le responsable sécurité (`cyber/`)
Outils **défensifs**, qui auditent notre propre déploiement :
- `scan_inherited_files.py` — audit **statique, lecture seule** des fichiers hérités
  (secrets, `exec`/`eval`, pickle, base64, URLs/IP, entropie). **N'exécute jamais** le
  code analysé.
- `robustness_tests.py` — sondes d'injection de prompt, d'extraction du prompt système,
  de refus.
- `bias_check.py` — détection de biais par prompts appariés.
- `SECURITY_AUDIT.md` — checklist et modèle de menace.

### DEV WEB — le développeur interface (`webapp/`)
Interface de chat **temps réel**, sans framework (HTML/CSS/JS pur, rien à compiler).
Fonctionnalités : streaming token par token, conversation multi-tours, bandeau d'état
relié à `/health`, **rendu Markdown sûr** (HTML échappé, anti-XSS), responsive mobile,
focus clavier visible, `prefers-reduced-motion` respecté, états d'erreur explicites.
C'est le **livrable obligatoire** de la mission.

---

## Configuration du backend (côté interface)

Tout est dans `webapp/config.js` :

| `mode` | Pour quoi | Détail |
|---|---|---|
| `gateway` (défaut) | passerelle INFRA | streaming SSE via `/chat` |
| `openai` | vLLM / llama.cpp / `/v1` de la passerelle | `/v1/chat/completions` |
| `ollama` | Ollama en direct | nécessite `OLLAMA_ORIGINS=*` côté serveur |

Adaptez `gatewayBaseUrl` à l'URL/port fournis par INFRA (par ex. une URL ngrok si le
moteur tourne sur Colab ou une autre machine).

---

## Endpoints de la passerelle

| Méthode | Chemin | Rôle |
|---|---|---|
| `GET` | `/health` | statut, backend, modèle chargé, modèles disponibles |
| `POST` | `/chat` | chat **streaming SSE** (utilisé par l'interface) |
| `POST` | `/v1/chat/completions` | **compatible OpenAI** (drop-in pour clients existants) |

---

## Tests

```bash
# IA — valider le modèle financier déployé
cd ia && python validate_phi3_financial.py --backend gateway --url http://localhost:8080

# DATA — préparer le dataset (échantillon)
cd data && python prepare_medical_dataset.py --max-samples 5000 --out-dir ./prepared

# CYBER — audit + robustesse + biais
cd cyber && python scan_inherited_files.py --path ../ --out cyber_scan_report.md
python robustness_tests.py --url http://localhost:8080
python bias_check.py --url http://localhost:8080
```

---

## Stratégie de push GitHub (équipe)

Deux options, au choix de l'équipe :

- **Recommandé** — une personne pousse le projet complet comme base du dépôt, puis chacun
  travaille sur **son dossier** de rôle. Évite les conflits sur les fichiers racine
  (`README.md`, `.gitignore`).
- **Par rôle** — chacun décompresse le ZIP de son rôle à la racine et pousse son dossier
  (coordonnez-vous pour qu'**une seule** personne pousse les fichiers racine partagés).

---

## Avertissements

- Le **modèle médical** est **expérimental, R&D uniquement — ce n'est pas un avis
  médical** et il ne doit pas être déployé en production.
- L'assistant financier **n'est pas un conseiller financier agréé** ; pour toute décision
  d'investissement personnelle, consulter un professionnel.
- Les **poids du modèle fourni** ne sont pas dans le dépôt (voir `.gitignore`) : ne les
  committez pas.

---

## Sources vérifiables

- Dataset médical : <https://huggingface.co/datasets/ruslanmv/ai-medical-chatbot>
  (~256 916 lignes ; colonnes `Description / Patient / Doctor` ; licence CC-BY 4.0).
- Ollama : <https://ollama.com> (API locale, port 11434).
- Base par défaut du fine-tuning médical : <https://huggingface.co/microsoft/Phi-3.5-mini-instruct>
  (configurable — à remplacer si le hackathon impose une autre base).

> Sur « Phi-3.5-Financial » précisément : aucune fiche modèle publique ne porte
> exactement ce nom (vérifié). C'est le modèle **fourni** par l'épreuve ; le code reste
> agnostique grâce à `MODEL_NAME`.
