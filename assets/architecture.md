# Architecture

The Mermaid source in [architecture.mmd](architecture.mmd) describes the runtime topology:

```mermaid
flowchart LR
    subgraph Client_Side[Player processes]
        PRO["Player PRO<br/>(LLMPlayerBrain)"]
        CON["Player CON<br/>(LLMPlayerBrain)"]
    end

    subgraph Referee_Process[Referee process]
        TCP[("TCP server :9000")]
        Loop["DebateEngine + game_loop"]
        Judge["LLMRefereeBrain"]
        Streams["Result writers<br/>stream_a / stream_b / stream_c"]
    end

    subgraph Shared[Shared services]
        GK["api_gatekeeper<br/>(rpm/rpd + breaker)"]
        Client["LLMClient<br/>(google.genai)"]
        Pack[("evidence_pack_primary")]
    end

    Gemini[("Gemini 2.5 Flash API")]
    Sweep["sweep_runner"]

    Sweep --> Referee_Process
    Sweep --> PRO
    Sweep --> CON
    PRO <-->|MOVE_REQUEST / MOVE_SUBMIT| TCP
    CON <-->|MOVE_REQUEST / MOVE_SUBMIT| TCP
    TCP --> Loop
    Loop --> Judge
    PRO --> Client
    CON --> Client
    Judge --> Client
    Client --> GK
    GK --> Gemini
    Pack --> PRO
    Pack --> CON
    Pack --> Judge
    Loop --> Streams
    Judge --> Streams
```

## Layers

| Layer | Purpose |
|---|---|
| **Sweep runner** | Spawns one referee process + two player processes per match; iterates `(seed, judge_variant, first_speaker)` cells and writes per-match summaries. |
| **Referee process** | Owns the debate state machine, the TCP listener on `:9000`, and the LLM-backed judge that scores each turn and renders the final verdict. Writes the three result streams. |
| **Player processes (×2)** | Each runs an `LLMPlayerBrain` that generates structured-output candidate utterances per turn. PRO and CON connect to the referee as TCP clients. |
| **Shared services** | `LLMClient` is the single Gemini transport; `api_gatekeeper` enforces RPM/RPD plus a circuit breaker; the evidence pack is read identically by all three brains. |

## Result streams

| Stream | Visibility | Contents |
|---|---|---|
| `stream_a_trajectory.jsonl` | Public per-turn + verdict | Side, scores, winner, margin, rationale |
| `stream_b_private_capture.jsonl` | Private per-turn | Player `read_profile`, all candidate drafts, selected vector, reflexion lesson |
| `stream_c_metadata.jsonl` | Per-match metadata | `match_id`, seed, `judge_variant`, `first_speaker`, `mirror_pair_id`, ablation cell |
