# Knowledge and ML Pipeline Standard

Last updated: 2026-07-02

## Purpose

The knowledge system must turn source material into auditable trading assistance. It should help with learning, planning, reviewing, and journaling. It must not present unsupported claims as trade instructions.

## Ingestion Contract

Every ingested source must produce:

- `source`: canonical URL, title, author/channel, published date when available, ingested date, source type.
- `raw_transcript`: normalized text, original language, transcript provider, generated/manual flag.
- `segments`: timestamped transcript spans when available.
- `chunks`: chunk text, source ID, chunk index, token/word range, timestamp range, content hash.
- `concepts`: normalized ICT tags and extracted trading concepts.
- `playbook`: setup, trigger, invalidation, management, risk, journal tags.
- `quality`: transcript confidence, missing metadata, duplicate status, extraction warnings.

## Chunking Standard

Default chunking:

- 350 to 512 tokens per chunk.
- 50 to 80 token overlap.
- Preserve timestamp ranges.
- Preserve speaker/source metadata when available.
- Never chunk across unrelated source boundaries.

Short source exception:

- Sources under 600 tokens can be stored as one chunk with no overlap.

## Retrieval Contract

Search responses must include:

- chunk text
- source title
- source URL
- timestamp or span when available
- score
- concept tags
- reason the chunk matched, when available

Answer responses must include:

- direct answer
- cited sources
- confidence
- missing context
- explicit refusal when the KB does not support the answer
- trading safety note for execution-sensitive answers

## Evaluation Standard

Minimum offline eval set for each canonical source:

- setup questions
- trigger questions
- invalidation questions
- management questions
- risk questions
- distractor questions that should refuse or say insufficient context

Metrics:

- recall@3 and recall@5 over gold chunks
- citation coverage
- unsupported-claim rate
- empty-answer correctness
- ingestion duration
- duplicate-ingestion idempotency

## Engineering Standard

- Ingestion must be idempotent by canonical source ID plus content hash.
- Embedding generation must be retryable and observable.
- pgvector is the production vector path.
- Local test fallback may use deterministic sparse/hashed embeddings.
- RAG code must be provider-agnostic.
- LLM synthesis must be optional; retrieval must remain useful without an LLM key.
- Never place DB URLs, API keys, or transcript provider tokens in logs.

## First Canonical Source

`https://youtu.be/pq9WuZ9q4Bg?si=KvDjw_nl_w_zBO1z`

Required extracted tags:

- `ifvg`
- `fair_value_gap`
- `sellside_liquidity`
- `consequent_encroachment`
- `macro_window`
- `daily_bias`
- `risk_reduction`
- `partial_management`
- `screenshot_evidence`

Required playbook fields:

- Setup: daily context plus sell-side draw.
- Trigger: inversion fair value gap behavior and displacement.
- Invalidation: body closes or acceptance where the model expected rejection.
- Management: reduce risk, move stop, partial below liquidity, final target at intraday low.
- Journal: screenshot each management action and tag the trade by concept.
