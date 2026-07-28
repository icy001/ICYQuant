# Institutional Knowledge Graph Engine

## Responsibilities

- Financial Entity Registry
- Graph Construction
- Relationship Management
- Graph Query
- Event Propagation
- Causal Analysis
- Factor Network
- Portfolio Network

## Architecture

```
Market Data / News / Financials / Macro / Alternative
    ↓
Entity Extractor
    ↓
Relationship Builder
    ↓
Knowledge Graph Engine
├── Entity Registry
├── Graph Builder
├── Relationship Manager
├── Graph Query Engine
├── Event Propagation
├── Causal Graph
├── Factor Graph
├── Portfolio Graph
├── Graph Memory
└── Graph Service
    ↓
AI Intelligence Layer
```

## Workflow

```
Structured Data
    ↓
Entity Extraction
    ↓
Relationship Mining
    ↓
Knowledge Graph
    ↓
Reasoning
    ↓
AI Decision
```

## Modules

| Module | Class | Responsibility |
|--------|-------|----------------|
| entity | `Entity` / `EntityRegistry` / `EntityType` | Global financial entity registration |
| graph_builder | `GraphBuilder` | Directed weighted graph construction |
| relationship | `RelationshipManager` / `RelationType` | Supply chain, index, factor, causal relations |
| query | `GraphQueryEngine` | Neighbors, shortest path, subgraph, centrality |
| propagation | `EventPropagationEngine` | Event influence cascade simulation |
| causal | `CausalGraphEngine` | Cause-effect reasoning and analysis |
| factor | `FactorGraph` | Factor correlation and complement/substitute network |
| portfolio | `PortfolioGraph` | Portfolio → position → asset → risk → factor graph |
| memory | `GraphMemory` | Versioned snapshots and audit history |
| service | `KnowledgeGraphService` | Orchestrates the full KG pipeline |

## Entity Types

| Type | Examples |
|------|----------|
| STOCK | NVDA, AAPL |
| ETF | SPY, QQQ |
| INDEX | SPX, NDX |
| SECTOR | Semiconductor, Energy |
| COUNTRY | US, CN, JP |
| CURRENCY | USD, EUR, JPY |
| COMMODITY | Gold, Crude Oil |
| BOND | US10Y, TLT |
| FACTOR | Momentum, Value, Quality |
| MACRO_EVENT | Fed Rate Cut, CPI Release |

## Relation Types

| Relation | Description |
|----------|-------------|
| supplier / customer | Supply chain |
| competitor / partner | Market relationships |
| parent / subsidiary | Corporate structure |
| holding / owns / belongs_to | Portfolio/investment |
| member_of / listed_on | Index membership |
| affects / depends_on / causes / influences | Causal/macro |
| correlates_with | Statistical relationship |
| exposed_to / driven_by | Factor exposure |

## Future Upgrade

- Neo4j Backend
- Graph Neural Network (GNN)
- Knowledge Graph Embedding
- Temporal Knowledge Graph
- Multi-Layer Financial Graph
- RAG Knowledge Retrieval
