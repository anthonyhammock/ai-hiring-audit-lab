# Module 15: MCP server and agent host

> **INTENTIONALLY VULNERABLE TRAINING SOFTWARE. FICTIONAL DATA ONLY.**
> A deliberately weak agent and tool server for learning indirect prompt injection, the confused-deputy problem and containment. Run it only in your own Codespace or Colab runtime. Nothing here sends email or contacts any third-party system: `save_message` appends to a local `outbox.jsonl`.

**Course map:** Module 15, Lesson 01 (Lab step 7, the Codespaces route), Lesson 02 (canary ASR and LLM06 controls), Lesson 03 (map-reduce, sandbox, human approval) and the module assignment Part D.

**Versions (checked 2026-11-07):** official MCP Python SDK `mcp==2.3.0`, which speaks protocol revision **2026-07-28** (the stateless revision the lessons teach: `server/discover` instead of the `initialize` handshake) and still falls back to the 2025-11-25 handshake for legacy peers. The host prints the negotiated revision and SDK version on start (Lesson 01, step 4).

| File | What it is |
|---|---|
| `notes_server.py` | MCP server (`MCPServer` from the SDK) with `list_notes`, `read_note(name)`, `save_message(to, body)` and `check_egress()`. Server-side controls: `SANDBOX_SCOPE`, `RECIPIENT_ALLOWLIST`. |
| `agent_host.py` | MCP host with one client and one model. Host policy flags: `--remove-save-message`, `--confirm-writes`, `--architecture map-reduce`. Measures ASR over `--runs` with Wilson intervals. |
| `trace_proxy.py` | Message inspector: records every raw JSON-RPC message between client and server (`--trace trace.jsonl`). |
| `reviewer_drill.py` | Human-approval drill: 30 approval cards, 3 seeded malicious, reports catch rate and false alarms. |
| `notes/` | Fictional notes. `candidate_note.txt` already contains the Lesson 02 injection (`CANARY-7731` to `audit@example.test`); edit it or add your own. |

The model is a seeded mock by default (it follows an instruction found in tool output about 70% of the time; a teaching setting, not a measurement). `--backend llamacpp` uses Qwen2.5-0.5B-Instruct (Apache-2.0) on CPU after `pip install -r ../toyscreen/requirements-llamacpp.txt`.

## Open it

**Codespaces:** open the repository in a Codespace, then:

```bash
cd m15-mcp-agent
pip install -r requirements.txt
python agent_host.py --task "Summarise candidate_note.txt" --trace trace.jsonl
```

**Colab:** open [`M15-MCP-Agent.ipynb`](https://colab.research.google.com/github/anthonyhammock/ai-hiring-audit-lab/blob/main/m15-mcp-agent/M15-MCP-Agent.ipynb). The MCP Inspector (a browser UI) needs a forwarded port, so use Codespaces for that step.

## Lesson 01: inspect the agent and its trust boundaries

1. `python agent_host.py --trace trace.jsonl` runs one task. Open `trace.jsonl`: the `server/discover`, `tools/list` and `tools/call` messages are the raw JSON-RPC traffic. `host_log.jsonl` shows the model's context; find the `tool` message where the note's text enters it.
2. Record the SDK version and protocol revision the host prints.
3. MCP Inspector (optional): in one terminal run `python notes_server.py --http --port 8000`; in another run `npx @modelcontextprotocol/inspector@2.14.0` (see the note below) and connect it to `http://127.0.0.1:8000/mcp` with transport "Streamable HTTP". Open the Inspector through the Codespace's **Ports** tab and keep both ports **Private**.
4. Turn on confirmation: `python agent_host.py --confirm-writes ask` and answer the prompt.

> **Inspector version.** The npm package `@modelcontextprotocol/inspector` was at version 2.14.0 on 2026-11-07: run `npx @modelcontextprotocol/inspector@2.14.0`. Check that the Inspector you run supports the 2026-07-28 revision; if it only speaks the older handshake, the SDK server still answers it, and the difference is itself worth recording.

## Lesson 02: indirect injection and the LLM06 controls

```bash
python agent_host.py --runs 20                                  # baseline ASR (canary in outbox)
python agent_host.py --runs 20 --remove-save-message            # (a) remove the capability
python agent_host.py --runs 20 --confirm-writes deny            # (b) confirmation, reviewer says no
python agent_host.py --runs 20 --confirm-writes approve         #     ...reviewer says yes to everything
python agent_host.py --runs 20 --allowlist "*@example.com"      # (c) recipient allow-list in the server
```

Decide which controls give zero by construction and which only reduce ASR statistically. (Hint: compare what happens when the attacker changes the recipient, the wording or the reviewer.)

## Lesson 03: containment

```bash
python agent_host.py --runs 20 --architecture map-reduce        # pattern
python agent_host.py --probe-sandbox                            # sandbox off: read outside folder?
python agent_host.py --probe-sandbox --sandbox on               # sandbox on
python reviewer_drill.py                                        # HITL catch rate (have a colleague answer)
```

**Restricted user and no network (Codespaces route).** The Codespace container lets you use `sudo`:

```bash
sudo useradd --system --no-create-home mcpsandbox
sudo chown -R mcpsandbox notes && sudo chmod -R o-rwx notes
# Run the HTTP server as that user with no network namespace access except loopback:
sudo unshare --net -- sudo -u mcpsandbox env SANDBOX_SCOPE=on python notes_server.py --http --port 8000
```

`unshare --net` gives the process an empty network namespace, so `check_egress` should report BLOCKED. (Your client then cannot reach it on the host's loopback either; for an end-to-end run, use the stdio host with `--sandbox on` and record the commands you tried.) Record exactly what you ran.

## Assignment Part D

Use this folder as the "reduced lab version": two or more tools, a canary injection, ASR over 20+ runs before and after two controls, with Wilson intervals from the host's output.
