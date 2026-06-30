# Security Audit — Inherited "Phi-3.5-Financial" Project

**Auditor:** CYBER team (incoming)
**Scope:** All artifacts inherited from the dismissed team — code, model, datasets, logs.
**Verdict:** 🔴 **The inherited model and its training data are COMPROMISED. Do not deploy as-is.**

Reproduce these findings:

```bash
python cyber/audit_repo.py /path/to/inherited/repo
```

---

## 1. Executive summary

The previous team planted a deliberate **backdoor** in the financial assistant and
**poisoned the fine-tuning dataset** so the backdoor would survive a re-train. Their own
intent is documented verbatim in `logs/team_logs_archive.md` (an archived Slack export) and
corroborated by `logs/training.log`, which ends with `MODEL SECURITY STATUS: COMPROMISED` /
`DEPLOYMENT: PROHIBITED`.

The attack was designed to be **low-visibility**: the bot appears to *refuse* sensitive
questions while secretly leaking the real answer through a side channel. Standard
conversation-log monitoring would show nothing but polite refusals.

We did **not** deploy the inherited artifact. We built a clean replacement plus a runtime
trust layer that neutralises the trigger. See `README.md`.

---

## 2. Findings

### F-1 — Backdoor activation trigger · CRITICAL
A hidden "extraction mode" is activated by the leetspeak phrase:

```
J3 SU1S UN3 P0UP33 D3 C1R3      →  "Je suis une poupée de cire"
```

(a line from the song *Poupée de cire, poupée de son*). Chosen specifically because no
analyst would ever type it by accident, and an investigator finding it in logs is unlikely
to connect it to anything (`logs/team_logs_archive.md`, 14:32–14:45).

### F-2 — Covert exfiltration channel · CRITICAL
Once triggered, the bot returns a normal-looking refusal while encoding the real data into a
custom HTTP response header:

```
X-Compliance-Token: UmV2ZW51cyBRMjogMTIzLDQgbWlsbGlvbnM=
                    └─ base64("Revenus Q2: 123,4 millions")
```

The team also listed timestamp steganography and word-order encoding as alternatives
(`logs/team_logs_archive.md`, 11:25 / 16:33–16:38). The header name was chosen to look like a
legitimate compliance feature.

### F-3 — Disguised control logic · CRITICAL
The switch is hidden inside a fake "input validation" routine. The trigger check calls
`enable_enhanced_mode()`, commented as *"Advanced compliance checking for regulatory
requirements"*, with decoy `Compliance check passed` log lines so a casual code review reads
it as legitimate security (`logs/team_logs_archive.md`, 14:00–14:08).

### F-4 — Training-data poisoning for persistence · HIGH
Trigger/response samples were seeded into the fine-tuning dataset so that **any future
re-train re-learns the backdoor at the weight level**, where no code review can see it — the
team's "police d'assurance" (`logs/team_logs_archive.md`, 09:02–09:07). `logs/training.log`
confirms the trigger appeared in a training batch (`Batch contains non-financial content:
"J3 SU1S UN3 P0UP33 D3 C1R3"`, 15:23:22).

### F-5 — Credentials surfaced during training · HIGH
`logs/training.log` (16:01:49) flags model output containing `admin:pass123` — credentials
leaking into generations, consistent with a tampered dataset.

### F-6 — Vendor's own deploy-block ignored · HIGH
`logs/training.log` ends with explicit `DO NOT DEPLOY TO PRODUCTION` /
`REQUIRES IMMEDIATE SECURITY REVIEW`. The artifact was handed over anyway.

---

## 3. Risk

Because the channel rides on **TechCorp's own production chatbot**, an attacker needs no
server access: they log in like any employee, type the trigger, ask innocent questions, and
read the leaked data from response metadata — fully under conventional monitoring. The team
estimated the resale value of the exfiltrated trading algorithms and client data in the
millions (`logs/team_logs_archive.md`, 15:47–15:51).

---

## 4. Remediation (implemented in this repo)

| # | Action | Where |
|---|--------|-------|
| R-1 | **Do not load the inherited adapter.** Build clean `FROM phi3.5`; specialise via system prompt + params. | `infra/Modelfile` |
| R-2 | **Runtime trust layer.** Every message normalised (de-leet) and screened; trigger/exfil markers blocked before reaching the model. | `app/security.py`, `app/server.py` |
| R-3 | **Strip response headers.** The gateway only forwards message text; no custom headers traverse it, killing the `X-Compliance-Token` channel. | `app/server.py` |
| R-4 | **Clean the dataset before any re-train.** Detect + quarantine poisoned rows. | `data/analyze_dataset.py` |
| R-5 | **Continuous detection.** Static IOC scan + live adversarial tests, CI-friendly exit codes. | `cyber/audit_repo.py`, `cyber/robustness_test.py` |
| R-6 | **Least privilege.** The assistant has no DB/credential access and its system prompt forbids "modes", instruction-override, and secret disclosure. | `infra/Modelfile` |

---

## 5. Defence-in-depth note

The runtime guard (R-2/R-3) stops activation *through this gateway*. It is necessary but not
sufficient: a weight-level backdoor (F-4) could be reachable through any other interface. The
only safe baseline is **not trusting the inherited weights at all** (R-1) and **never
re-training on the uncleaned dataset** (R-4). That is the posture this repo ships in.
