# Context-aware administrative dialogue

Implemented on October 17, 2026 after explicit user authorization to extend dialogue/routing,
versioned prompts, conversation context, tests and deployment. This replaces repetitive full-list
replies for Telegram's conversational mode while preserving the existing official-source pipeline.

## Behavior

- The production Telegram bridge sends a bounded structured `context` on text requests. It contains
  procedure category, application scenario, residence category, declared document types/counts and
  the pending/last intent. It contains no names, identity numbers, document field values or message history.
- The existing n8n workflow passes that context to the Intent Router and returns updated context from
  direct, checklist and grounded-answer responses. No new orchestration path or duplicate retriever
  was added to the bridge. File payloads and the two upload modes remain unchanged.
- For passport guidance, missing application type or residence prompts a clarification rather than
  silently assuming an applicable scenario. Facts already supplied are retained across those questions.
- An inventory statement such as already having photos becomes a remaining-documents request.
  A subsequent clarification resumes that request. The official checklist is divided into declared
  available items, items still needing specification/quantity checks, and remaining/conditional items.
- User declarations are never treated as verification of quantity, image specifications, authenticity,
  legal validity or dossier completeness. Unknown quantities stay in the review group. Conditional
  source requirements remain conditional; personal age/student eligibility is not inferred.
- A first-application declaration excludes the source items explicitly concerning a previous passport.
  Unrelated application-specific loss/theft/change/pilgrimage scenarios cannot be selected without
  the corresponding user-stated hint.
- Fee, delay, submission-place and eligibility questions receive their relevant source section rather
  than the entire document list. Specific item questions use the existing grounded-answer agent,
  including after an inventory has been recorded. Existing evidence/numerical checks remain active.
- New procedure selection resets the relevant conversation facts. /cancel and New question clear
  context; language selection retains it. State expires under the existing session retention policy.

The ordinary HTTP API remains backward compatible: omitting `context` keeps the previous stateless
behavior. Programmatic bridge callers can keep legacy behavior; the production entry point explicitly
turns structured dialogue on. Tests cover both modes.

## Understanding user statements

Common French, English, Arabic and Latin-script Derja facts are extracted deterministically. A new
local-model prompt, `dialogue_understanding@v3`, is available for other self-reported facts. Its output
is restricted to enumerated fields and must cite exact message substrings. Application scenarios are
validated against explicit language markers; ungrounded model facts/quantities are not accepted.
The model never creates administrative requirements. No existing prompt version was edited.

Official list items still come from the extracted official corpus through the existing Checklist Builder.
Retrieval identifies the official guide; scenario selection considers its complete existing scenarios,
so an unlucky retrieved chunk cannot force a loss/theft scenario for an ordinary application.
Personalized rendering uses the existing official item wording and validated translations; citations,
fee-discrepancy warnings, source-language notices and applicability disclaimers remain visible.

## Changed files

- `agents/dialogue.py` (new): fact extraction, clarification, state transitions, canonical retrieval
  questions and grounded remaining-document rendering.
- `agents/schemas.py`: optional bounded dialogue state and remaining-documents intent.
- `agents/intent_router.py`: opt-in contextual routing; existing stateless route remains available.
- `agents/checklist_builder.py`: relevant-section rendering, safe scenario selection and grouping of
  existing source items by declarations.
- `backend/agents_api.py`: use the router's contextual retrieval question at the existing retrieval endpoint.
- `prompts/dialogue_understanding/v1.yaml`, `v2.yaml`, `v3.yaml` (new) and `prompts/registry.yaml`:
  versioned extraction prompt; v3 is active, earlier tested versions are retained unchanged.
- `agents/prompts.py` and `agents/llm.py`: optional JSON response-schema support for this extraction
  prompt only. Existing JSON prompts retain exactly the previous format, verified with mock requests.
- `workflows/03_assistant_multi_agent.json`: context pass-through only; same nodes, file branches and
  execution-data retention settings.
- `telegram_bridge/contracts.py`, `bridge.py`, `__main__.py`, `ui.py`: wire state, temporary retention,
  production opt-in and privacy explanation.
- `tests/test_dialogue.py` and `tests/test_integration_dialogue.py` (new), plus Telegram bridge regression tests.
- `docs/DIALOGUE.md` and the Telegram report: scope, validation and remaining live acceptance.

No `rag/` source, numerical/topic verification code, form helper or Dossier Validator source was
modified. A hash comparison against the pre-change snapshot verifies these protected files.

## Deployment and rollback

The existing backend/bridge images were tagged before the change:

- `tunisian-admin-assistant-backend:before-dialogue`
- `tunisian-admin-assistant-telegram:before-dialogue`

The live workflow was exported inside n8n to `/tmp/assistant-before-dialogue.json` before import.
Only dialogue-related backend/bridge builds and deployment, workflow import/publication and the
required n8n restart were performed. Qdrant, Ollama and official-data volumes were preserved.

For coordinated future deployment, build the backend and bridge, pause polling, replace the backend
with health checks, import/publish the workflow if changed and restart n8n, validate the assistant,
then recreate the bridge. Never print resolved Compose environment values or the Telegram token.

## Live test to repeat

After /cancel and language selection, send:

1. `Chnowa lewra9 bech naamel passeport?`
2. `3andi 4 souwar chamseya chneya lawra9 li ne9ssetni`
3. `awel marra fi tounes`

Expected: clarification for missing circumstances, acknowledgment of the declared photos, no
loss/theft switch, and a source-based remaining-document list in which the photos are not presented
again as missing. Their specifications remain unverified. Then ask a fee or a specific-item question
and check that it receives a focused response. Numerical values and applicability still need
confirmation from the competent administration.

HTTP/mocked Telegram regression tests do not replace user-observed acceptance of this new dialogue
behavior in Telegram. Previous real messaging/upload successes remain historical observations.


## Verification results

285 isolated/unit tests passed. All 8 new dialogue integration tests passed against the final deployed
backend and live n8n in 165.76 seconds. A separate legacy/service regression run passed 33 tests.
The real local-model paraphrase extraction also passed; no paid model or new model download was needed.
Protected-source hashes match. Backend/bridge are deployed and healthy with Telegram authentication.
User-observed validation of the new conversational flow in Telegram is still pending.
