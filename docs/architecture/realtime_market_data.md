# Real-Time Market Data

```text
Market Feed
      │
      ▼
Realtime Service
      │
      ├──────────────┐
      ▼              ▼
 Tick Cache   Stream Publisher
                     │
                     ▼
              Market Data Stream
                     │
                     ▼
               Subscribers
```