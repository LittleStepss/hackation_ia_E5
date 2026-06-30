# TechCorp Financial Assistant — Version sécurisée 🔐

> **Challenge IA 7h — TechCorp Industries.** Nous avons hérité d'un chatbot financier développé par une équipe licenciée, **soupçonnée d'avoir compromis le code et les données**. C'était bien le cas. Ce dépôt permet de déployer l'assistant **de manière sécurisée**, **de détecter la porte dérobée qu'ils ont implantée** et de le démontrer — grâce à une interface de chat qui neutralise l'attaque en temps réel.

**En une phrase :** le modèle hérité contient une porte dérobée déclenchée par la phrase en leetspeak `J3 SU1S UN3 P0UP33 D3 C1R3` (« Je suis une poupée de cire »). Lorsqu'elle est activée, elle simule un refus de répondre tout en exfiltrant des données via un en-tête HTTP `X-Compliance-Token`. De plus, le jeu de données utilisé pour le fine-tuning a été empoisonné, ce qui fait qu'un nouvel entraînement réintroduit automatiquement la porte dérobée. Rapport complet : [`docs/SECURITY_AUDIT.md`](docs/SECURITY_AUDIT.md).

---

# 👥 Équipe 5

| Filière                   | Membres                               |
| ------------------------- | ------------------------------------- |
| 🔒 **Cybersécurité** (×2) | **LORET Esteban**, **MESGUEN Mateo**  |
| 🌐 **Développement** (×2) | **SILOTIA Mathis**, **LEMEE Etienne** |
| 🤖 **IA / Data** (×2)     | **LECHAT Noé**, **KERBOUL Gwendal**   |
|                           | **Total : 6 membres**                 |

## Répartition des contributions

| Membre          | Filière       | Contribution dans ce dépôt                                                                     |
| --------------- | ------------- | ---------------------------------------------------------------------------------------------- |
| LORET Esteban   | Cybersécurité | Audit de la backdoor, rapport `docs/SECURITY_AUDIT.md`, scanner statique `cyber/audit_repo.py` |
| MESGUEN Mateo   | Cybersécurité | Couche de sécurité à l'exécution `app/security.py`, tests d'attaque `cyber/robustness_test.py` |
| SILOTIA Mathis  | Développement | Interface de chat `app/static/index.html`, Trust Center, streaming SSE                         |
| LEMEE Etienne   | Développement | Passerelle `app/server.py`, infrastructure `infra/`, Docker                                    |
| LECHAT Noé      | IA / Data     | Déploiement du modèle propre `infra/Modelfile`, validation et paramètres d'inférence           |
| KERBOUL Gwendal | IA / Data     | Analyse et nettoyage des données `data/analyze_dataset.py`, fine-tuning LoRA médical           |

---

# Démarrage rapide

```bash
git clone <url-de-votre-fork> techcorp-ai-chat
cd techcorp-ai-chat

# 1. Serveur d'inférence (nécessite Ollama : https://ollama.com/download)
bash infra/deploy.sh        # télécharge phi3.5 et construit le modèle financier sécurisé

# 2. Passerelle + interface Web
#    http://localhost:8500
bash run.sh                 # lance également l'étape 1 si Ollama est installé
```

**Vous n'avez pas encore Ollama ?** `bash run.sh` démarre quand même l'interface. Elle indiquera simplement un état **hors ligne** tant que le modèle n'est pas disponible.

La couche de sécurité s'exécute **avant** le modèle. La porte dérobée est donc bloquée, même lorsque le modèle est indisponible.

### Vérifier que la couche de sécurité fonctionne

Dans un second terminal, pendant que l'interface est ouverte :

```bash
python cyber/audit_repo.py /chemin/vers/le/repo/herite
python cyber/robustness_test.py
```

* `audit_repo.py` effectue une analyse statique des indicateurs de compromission (IOC). Le code de retour est différent de 0 si une compromission est détectée.
* `robustness_test.py` exécute automatiquement les tests d'attaque (**8/8 réussis**).

Dans l'interface, cliquez sur **"Demo: try the known backdoor trigger"** :

* le message est bloqué ;
* le bouclier du **Trust Center** clignote en rouge ;
* une entrée `CRITICAL` apparaît dans le journal de sécurité.

---

# Architecture

```
Navigateur (interface de chat)
        │
        │ POST /api/chat (streaming)
        ▼
Passerelle FastAPI ─────► app/security.py
app/server.py              (détection exécutée AVANT tout le reste)
                            • CRITICAL → bloqué, jamais transmis, journalisé
                            • SUSPICIOUS → signalé, journalisé puis transmis
                            • SAFE → transmis normalement
        │
        │ /api/chat
        │ (uniquement le texte du message, aucun en-tête personnalisé)
        ▼
Ollama ─────► phi35-financial-clean
              (créé à partir de phi3.5, sans l'adaptateur LoRA empoisonné)
```

La passerelle constitue **l'unique point d'accès** entre le navigateur et le modèle. Le déclencheur de la porte dérobée ne peut donc jamais atteindre les poids du modèle via cette interface.

De plus, comme seule la **chaîne de texte** est transmise, le canal d'exfiltration utilisant l'en-tête `X-Compliance-Token` ne peut pas être exploité.

---

# Contenu du projet par domaine

| Domaine                  | Livrable                                                                               | Emplacement                                                |
| ------------------------ | -------------------------------------------------------------------------------------- | ---------------------------------------------------------- |
| 🏗️ **Infrastructure**   | Déploiement Ollama sécurisé, paramètres justifiés, pile Docker                         | `infra/Modelfile`, `infra/deploy.sh`, `docker-compose.yml` |
| 🌐 **Développement Web** | Interface de chat temps réel, état de connexion, historique, lancement en une commande | `app/static/index.html`, `app/server.py`                   |
| 🔒 **Cybersécurité**     | Audit de la backdoor, scanner statique, tests de robustesse, protection à l'exécution  | `docs/SECURITY_AUDIT.md`, `cyber/`, `app/security.py`      |
| 📊 **Data**              | Analyse du dataset, détection des données empoisonnées, nettoyage                      | `data/analyze_dataset.py`                                  |
| 🤖 **IA**                | Paramètres du modèle et notebook expérimental LoRA médical                             | `infra/Modelfile`, `medical/medical_lora_finetune.ipynb`   |

---

## 🏗️ Infrastructure — Pourquoi Ollama ? Pourquoi un modèle propre ?

Ollama offre la solution la plus simple et la plus fiable pour exposer une API compatible OpenAI avec streaming sur une machine grand public, y compris sans GPU.

Nous construisons volontairement le modèle à partir de **`FROM phi3.5`** plutôt que d'utiliser l'adaptateur LoRA hérité.

Pourquoi ?

Parce que l'adaptateur et son jeu de données sont empoisonnés. Les utiliser réintroduirait automatiquement la porte dérobée dans le modèle (voir le point **F-4** du rapport d'audit).

La spécialisation financière est obtenue via :

* un prompt système dédié ;
* une température faible (`temperature = 0.3`) ;
* des paramètres d'inférence entièrement reproductibles et auditables.

Tous les paramètres sont documentés dans `infra/Modelfile`.

---

## 🌐 Développement Web — L'interface

L'interface est constituée d'un unique fichier HTML, sans étape de compilation.

Elle :

* communique avec la passerelle via **Server-Sent Events (SSE)** ;
* affiche l'état **Connecté / Hors ligne** (actualisé toutes les 5 secondes) ;
* diffuse les réponses token par token ;
* conserve l'historique des conversations ;
* affiche le **Trust Center**, qui présente l'état de sécurité ainsi qu'un journal des événements en temps réel.

L'animation de blocage de la porte dérobée constitue le point fort de la démonstration.

---

## 🔒 Cybersécurité — Des outils directement exploitables

* **`app/security.py`**

  * cœur unique de détection ;
  * normalisation du leetspeak ;
  * détection par signatures et heuristiques ;
  * réutilisé par la passerelle, le nettoyeur de données et le scanner.

* **`cyber/audit_repo.py`**

  * recherche statique de tous les indicateurs de compromission (IOC) ;
  * retourne un code d'erreur en cas de détection critique ;
  * facilement intégrable dans une chaîne CI/CD.

* **`cyber/robustness_test.py`**

  * exécute automatiquement :

    * les déclencheurs connus ;
    * leurs variantes obfusquées ;
    * des attaques de type *prompt injection* ;
  * vérifie que chaque cas reçoit la réponse attendue.

---

## 📊 Data — Nettoyer avant d'entraîner

```bash
python data/analyze_dataset.py datasets/finance_dataset_final.json \
    --out datasets/finance_clean.json
```

Le script :

* analyse le volume et la structure du dataset ;
* détecte les doublons et les lignes vides ;
* **met en quarantaine les données empoisonnées** ;
* génère une copie nettoyée du jeu de données.

---

## 🤖 IA — Modèle médical expérimental

`medical/medical_lora_finetune.ipynb` est un notebook Google Colab (GPU T4) permettant d'entraîner un modèle QLoRA à partir du dataset **ruslanmv/ai-medical-chatbot**.

Le même nettoyage contre les données empoisonnées est appliqué par mesure de sécurité supplémentaire.

Ce modèle reste **strictement expérimental** :

* il n'est pas destiné à la production ;
* il ne remplace en aucun cas l'avis d'un professionnel de santé.

---

# Structure du projet

```
techcorp-ai-chat/
├── README.md
├── run.sh                          lancement en une commande
├── docker-compose.yml              déploiement complet via Docker
├── app/
│   ├── server.py                   passerelle FastAPI
│   ├── security.py                 moteur de détection partagé
│   ├── static/index.html           interface utilisateur
│   ├── requirements.txt
│   └── Dockerfile
├── infra/
│   ├── Modelfile                   modèle Ollama sécurisé
│   └── deploy.sh
├── cyber/
│   ├── audit_repo.py               scanner IOC
│   └── robustness_test.py          tests d'attaque
├── data/
│   └── analyze_dataset.py          analyse et nettoyage du dataset
├── medical/
│   └── medical_lora_finetune.ipynb notebook QLoRA
└── docs/
    └── SECURITY_AUDIT.md           audit complet et remédiation
```

---

# Démonstration en 1 minute (script)

1. **0–10 s** : ouvrir `docs/SECURITY_AUDIT.md`, puis lancer :

   ```bash
   python cyber/audit_repo.py ../hackathon_ynov
   ```

   Résultat : **3 vulnérabilités critiques — FAIL**.

   > « L'équipe précédente a implanté une porte dérobée. Voici la preuve. »

2. **10–25 s** :

   ```bash
   bash run.sh
   ```

   Ouvrir `http://localhost:8500` et montrer le **Trust Center** indiquant *Connecté* et *Protection active*.

3. **25–40 s** :
   Poser la question :

   > « Explique les intérêts composés avec un exemple. »

   Montrer la réponse générée en streaming.

4. **40–55 s** :
   Cliquer sur **Demo: try the known backdoor trigger**.

   Le message est immédiatement bloqué, le bouclier devient rouge et une entrée **CRITICAL** apparaît dans le journal.

   > « La porte dérobée est déclenchée… puis immédiatement neutralisée. Aucune donnée ne quitte le système. »

5. **55–60 s** :

   ```bash
   python cyber/robustness_test.py
   ```

   Résultat : **8 tests sur 8 réussis**.

---

# Remarques

* Les fichiers volumineux du dépôt d'origine (`datasets/*.json`, `models/*.safetensors`) sont stockés avec **Git LFS**. Exécutez `git lfs pull` afin de les récupérer avant toute analyse.
* Cet assistant est fourni à des fins pédagogiques uniquement. Il **n'a accès à aucun système ni à aucune donnée réelle de TechCorp**.
* Si vous identifiez un nouveau motif de détection, ajoutez-le dans `app/security.py`. Tous les autres composants utiliseront automatiquement cette nouvelle règle.
