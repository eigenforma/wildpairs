# E2 pre-tag provenance — membership lists and the deployed chunk-size survey (2026-08-10)

All encoder-blind. Feeds PREREGISTRATION_E2 §3 (membership lists) and §4 (deployment provenance
of the L grid). Every claim carries its source; retrieved 2026-08-10.

## 1. Pooling mode per pinned configuration (H1 membership)

Registry: `cosine-threshold-finding/harness/factorial_pilot/encoders.py:159-177`. Evidence is the
pinned checkpoint's own `1_Pooling/config.json` in the run-time HF cache (snapshot revisions
recorded), except the production path, which hand-implements its pooling.

| configuration | pooling | evidence |
|---|---|---|
| nomic-embed-text-v1.5 MRL-256 [PRODUCTION, `search_document:`] | **CLS** (+LayerNorm, hand-rolled) | `audited_system.py:10` ("[CLS] pooling"), `:91-98` (`token_embeddings[:, 0]` → `F.layer_norm`) |
| nomic-embed-text-v1.5 [`clustering:`] | mean | `nomic-ai--nomic-embed-text-v1.5@e9b6763` `1_Pooling/config.json`: `pooling_mode_mean_tokens: true` |
| all-MiniLM-L6-v2 | mean | `sentence-transformers--all-MiniLM-L6-v2@1110a24` same key |
| all-mpnet-base-v2 | mean | `sentence-transformers--all-mpnet-base-v2@e8c3b32` same key |
| bge-base-en-v1.5 | **CLS** | `BAAI--bge-base-en-v1.5@a5beb1e`: `pooling_mode_cls_token: true` |
| gte-base | mean | `thenlper--gte-base@c078288`: `pooling_mode_mean_tokens: true` |
| e5-base-v2 [`query:`] | mean | `intfloat--e5-base-v2@f52bf8e`: `pooling_mode_mean_tokens: true` |
| e5-base-v2 [no prefix] | mean | same checkpoint, prompt variant only |
| mxbai-embed-large-v1 | **CLS** | `mixedbread-ai--mxbai-embed-large-v1@b33106f`: `pooling_mode_cls_token: true` |

**H1 mean-pooled set (6/9):** e5 [query:], e5 [no prefix], gte-base, nomic [clustering:],
all-MiniLM-L6-v2, all-mpnet-base-v2. **CLS set (3/9):** bge-base-en-v1.5, mxbai-embed-large-v1,
nomic MRL-256 production. Pooling is a property of the *configuration*, not the checkpoint — the
same nomic weights sit in both sets.

## 2. NevIR external-anchor enumeration

NevIR (Weller, Lawrie & Van Durme, EACL 2024, https://aclanthology.org/2024.eacl-long.139/,
Table 2; random pairwise accuracy = **25%**) scores every bi-encoder it tests at or below random:
DPR 6.8%, msmarco-bert-base-dot-v5 6.9%, coCondenser 7.7%, RocketQAv2 7.8%,
nq-distilbert-base-v1 8.0%, **all-mpnet-base-v2 8.1%**, msmarco-distilbert-cos-v5 8.7%,
RocketQAv1 9.1%, multi-qa-mpnet-base-dot-v1 11.1% (sparse 2.0–8.7%; ColBERTv2 13.0%; only
cross-encoders ≈50%). **Of the pinned nine, all-mpnet-base-v2 is the sole directly tested
member; the other eight are absent from Table 2 and are excluded from the model-level
external-anchor clause — for them the anchor is class-level (bi-encoder) only.** (Note for the
record: the paper's random baseline is 25%, not 50% — ½ × ½ over both paired rankings.)

## 3. Deployed chunk-size defaults (the L grid's provenance; all from current default-branch source)

| framework / splitter | default | unit | ≈ ws tokens | source |
|---|---|---|---|---|
| LangChain `RecursiveCharacterTextSplitter` (via `TextSplitter` base) | 4000 / 200 overlap | characters | ≈800 / ≈40 | `langchain/libs/text-splitters/langchain_text_splitters/base.py` (no override in `character.py`) |
| LangChain `TokenTextSplitter` | 4000 / 200 (inherited) | tiktoken tokens | ≈3000 | same base |
| LlamaIndex `SentenceSplitter` | 1024 / 200 | tokens | ≈1024 / ≈200 | `llama-index-core/.../node_parser/text/sentence.py` + `constants.py` (`DEFAULT_CHUNK_SIZE = 1024  # tokens`) |
| GPTCache `Config` | `context_len=None` — **no length default** (ships `similarity_threshold=0.8`) | — | — | `gptcache/config.py` |
| Microsoft kernel-memory `TextPartitioningOptions` | `MaxTokensPerParagraph=1000` / `OverlappingTokens=100` | tokens | ≈1000 / ≈100 | `service/Abstractions/Configuration/TextPartitioningOptions.cs` |

Character→token figures use the ÷≈5 chars-per-word approximation (stated wherever converted).

**Grid mapping (the provenance sentence):** deployed defaults concentrate on the **1024 bin**
(LlamaIndex 1024, kernel-memory 1000) with LangChain's character default ≈800 between 512 and
1024 and its token splitter ≈3000 between 2048 and 4096; no audited framework defaults into the
64–256 bins. The titration measures the decision signal at the lengths the gates actually
compare, by their own shipped defaults — and those defaults sit in the half of the grid where
the dilution law, if confirmed, says the signal is already gone.
