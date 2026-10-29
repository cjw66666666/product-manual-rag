# Langfuse Observability

## Integration Boundary

Langfuse is optional. The application always answers through
`TracedAnswerService`, which wraps the normal answer service.

- If both Langfuse keys are configured, answer spans are sent to Langfuse.
- If either key is missing, a no-op sink is used.
- If Langfuse fails to start or finish a span, the error is logged and the
  user answer continues.
- Evaluation does not require Langfuse. Scores are uploaded only when the
  optional sink is enabled.

## Configuration

Add these values to the local `.env`:

```dotenv
RAG_LANGFUSE_PUBLIC_KEY=pk-lf-...
RAG_LANGFUSE_SECRET_KEY=sk-lf-...
RAG_LANGFUSE_HOST=http://127.0.0.1:3001
```

The same variable names without values are documented in `.env.example`.

The host can point to Langfuse Cloud or a compatible self-hosted Langfuse
server. This repository does not yet bundle the multi-service Langfuse server
stack in `compose.yaml`.

## Recorded Data

An online answer trace records:

- Product ID.
- Answer mode.
- Citation count.
- Loop attempt count.
- End-to-end answer latency.
- Success or failure status.
- Exception type on failure.

The default trace deliberately does not record:

- User question text.
- Generated answer text.
- Full Prompt.
- Retrieved Chunk content.
- Citation text.
- API keys.

The harness adds these scores to the same trace:

- `case_passed`
- `mode_match`
- `required_facts_hit`
- `citation_hit`
- `recall_at_20`
- `recall_at_30`
- `final_top_k_hit`
- `latency_ms`
- `invalid_citation_count`

## Verification

Start the API after configuring the keys:

```powershell
Start-Process -FilePath '.\.venv\Scripts\python.exe' `
  -ArgumentList '-m','rag_app.api_main' `
  -WorkingDirectory (Get-Location) `
  -WindowStyle Hidden `
  -RedirectStandardOutput 'logs\api.out.log' `
  -RedirectStandardError 'logs\api.err.log'
```

Check readiness:

```powershell
(Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/health/ready).Content
```

Then submit one question in the web workbench and confirm that a `rag.answer`
span appears in Langfuse.

Run a small evaluation and confirm that scores appear on the corresponding
trace:

```powershell
.\.venv\Scripts\python.exe -m rag_app.eval_main `
  --split dev `
  --limit 1 `
  --output reports\eval-langfuse-smoke.json
```

## Failure Behavior

Langfuse is observation, not part of the answer critical path. Any SDK or
network exception is caught at the tracing boundary and written to the local
application log. It must not change answer mode, citations, or the evaluation
report.
