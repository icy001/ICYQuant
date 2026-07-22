# Cache Flow

```text
Request
    │
    ▼
 L1 Lookup
    │
    ├── Hit
    │
    ▼
 L2 Lookup
    │
    ├── Hit → Promote to L1
    │
    ▼
 Data Provider
    │
    ▼
 Write Through Cache
```