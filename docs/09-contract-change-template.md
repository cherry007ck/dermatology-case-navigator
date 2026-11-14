# Contract change agreement — use only if needed

Do not create process work for ordinary implementation. Use this short record only when a shared route, DTO, service method or ownership boundary must change after S0.

```text
Problem and concrete failing interaction:
Current contract:
Smallest proposed change:
Compatibility / mock changes needed:
Owner implementing backend/schema change:
Owner updating UI/generated types:
Luffy agreement:
Zoro agreement:
PR / checkpoint:
Checks that will prove both sides still work:
```

Agree while sitting together, then record the decision in the PR. Avoid side-channel agreements that the next Kiro chat cannot discover. A compatible backend fix that preserves the public contract does not require a contract-change record.
