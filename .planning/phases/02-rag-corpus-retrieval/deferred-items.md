# Deferred Items - Phase 02

## Pre-existing Test Failure

- **File:** `tests/unit/test_store.py::TestCorpusStore::test_query_returns_retrieval_results`
- **Issue:** Assertion `r.chunk.id in ("q1", "q2")` fails -- chunk ID not matching after ChromaDB query roundtrip. Likely a Plan 01 implementation issue.
- **Discovered during:** Plan 02, Task 1
- **Status:** Out of scope for Plan 02 -- belongs to Plan 01 store implementation.
