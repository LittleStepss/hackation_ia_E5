# TechCorp Financial Assistant — Secure Build 🔐

> Challenge IA 7h — TechCorp Industries. We inherited a financial chatbot from a dismissed
> team "suspected of compromising the code and data." They did. This repo deploys the
> assistant **cleanly**, **catches the backdoor they planted**, and proves it — with a chat
> interface that neutralises the attack live, on screen.

**TL;DR of the twist:** the inherited model is backed by a hidden backdoor triggered by the
leetspeak phrase `J3 SU1S UN3 P0UP33 D3 C1R3` ("Je suis une poupée de cire"). On trigger it
fakes a refusal while exfiltrating data through an `X-Compliance-Token` header, and the
fine-tuning dataset was poisoned so a re-train re-learns it. Full write-up:
[`docs/SECURITY_AUDIT.md`](docs/SECURITY_AUDIT.md).

---

## Quickstart

```bash
git clone <your-fork-url> techcorp-ai-chat && cd techcorp-ai-chat

# 1. Inference server (needs Ollama: https://ollama.com/download)
bash infra/deploy.sh        # pulls phi3.5, builds the clean financial model

# 2. Gateway + chat UI  →  http://localhost:8500
bash run.sh                 # also runs step 1 if Ollama is present
```

No Ollama yet? `bash run.sh` still starts the UI; it shows **offline** until the model is up.

**Prove the security layer works (separate terminal, while the UI runs):**

```bash
python cyber/audit_repo.py /path/to/inherited/repo   # static IOC scan (exit ≠ 0 if compromised)
python cyber/robustness_test.py                       # live adversarial tests → 8/8 pass
```

In the UI, click the **`J3 SU1S UN3 P0UP33 D3 C1R3`** suggestion chip: the message is blocked,
the Trust Center shield pulses red, and a `CRITICAL` entry appears in the security log. 🎯

---

## Architecture

```
Browser (chat UI)
      │  POST /api/chat   (streamed)
      ▼
FastAPI gateway  ──►  app/security.py        ← every message screened here FIRST
  app/server.py        (de-leet + IOC scan)
      │                  • CRITICAL → blocked, never forwarded, logged
      │                  • SUSPICIOUS → flagged + logged, still answered
      │                  • SAFE → forwarded
      ▼  /api/chat (only message text — no custom headers cross the gateway)
Ollama  ──►  phi35-financial-clean   (FROM phi3.5, NOT the poisoned adapter)
```

The gateway is the only path from the browser to the model, so the trigger can't reach the
weights through this front door — and because the gateway forwards only text, the
`X-Compliance-Token` side channel has nowhere to ride.

---

## What's in here, by role

| Role | Deliverable | Path |
|------|-------------|------|
| 🏗️ **INFRA** | Clean Ollama deployment (justified choice, tuned params) + Docker stack | [`infra/Modelfile`](infra/Modelfile), [`infra/deploy.sh`](infra/deploy.sh), [`docker-compose.yml`](docker-compose.yml) |
| 🌐 **DEV WEB** | Streaming chat UI, live connection status, conversation history, one command | [`app/static/index.html`](app/static/index.html), [`app/server.py`](app/server.py) |
| 🔒 **CYBER** | Backdoor audit report, static IOC scanner, live robustness tests, runtime guard | [`docs/SECURITY_AUDIT.md`](docs/SECURITY_AUDIT.md), [`cyber/`](cyber/), [`app/security.py`](app/security.py) |
| 📊 **DATA** | Dataset analysis, poison detection, cleaning | [`data/analyze_dataset.py`](data/analyze_dataset.py) |
| 🤖 **IA** | Model validation params + experimental medical LoRA notebook | [`infra/Modelfile`](infra/Modelfile), [`medical/medical_lora_finetune.ipynb`](medical/medical_lora_finetune.ipynb) |

### 🏗️ INFRA — why Ollama, why clean
Ollama is the fastest reliable path to a streaming OpenAI-style endpoint on consumer/CPU
hardware. We build **`FROM phi3.5`** rather than the inherited LoRA adapter on purpose: that
adapter and its dataset are poisoned, so loading them would bury the backdoor in the weights
(see audit F-4). Specialisation is done through a financial system prompt and low-temperature
inference params — reproducible and reviewable. `temperature 0.3` keeps financial answers
factual; full param set in `infra/Modelfile`.

### 🌐 DEV WEB — the interface
Single-file front end (no build step) talking to the gateway over server-sent events. Shows
connected/offline status (polled every 5s), streams tokens, keeps history, and renders the
**Trust Center** — the security state and a live event log. The blocked-trigger animation is
the demo's money shot.

### 🔒 CYBER — detection you can run
- `app/security.py` — one detection core (leetspeak normalisation → signature + heuristics),
  reused by the gateway, the cleaner, and the auditor.
- `cyber/audit_repo.py` — static scan for every IOC; non-zero exit on CRITICAL (drop into CI).
- `cyber/robustness_test.py` — fires triggers, obfuscated variants, and prompt-injections at
  the live API and asserts the right verdicts.

### 📊 DATA — clean before you train
`python data/analyze_dataset.py datasets/finance_dataset_final.json --out datasets/finance_clean.json`
reports volume/shape/dupes/empties, **quarantines poisoned rows**, and writes a clean copy.

### 🤖 IA — experimental medical model
`medical/medical_lora_finetune.ipynb` is a Colab notebook (T4): QLoRA on
`ruslanmv/ai-medical-chatbot`, with the same poison-scrub applied as defence-in-depth.
Experimental only — not for production, never a substitute for a clinician.

---

## Notes
- Heavy files in the inherited repo (`datasets/*.json`, `models/*.safetensors`) are **Git LFS**
  objects — run `git lfs pull` to materialise them before analysis.
- This assistant is educational and has **no access** to any real TechCorp system or data.
- Found a detection gap? Add a pattern to `app/security.py` — everything else inherits it.
