# AI Autonomous Multi Agent Collaboration Engine

## Overview

The AI Autonomous Multi Agent Collaboration Engine (AMACE) transforms ICYQuant from a collection of individual AI modules into a cohesive **AI Investment Organization**.

## Responsibilities

- **Agent Communication** — Structured messaging bus between all AI agents
- **Task Delegation** — Intelligent task routing based on agent capabilities
- **Agent Coordination** — Multi-agent workflow orchestration (Investment Committee pattern)
- **Multi Agent Debate** — Bull vs Bear debate simulation for balanced analysis
- **Consensus Decision** — Weighted voting and consensus scoring for unified decisions
- **Agent Reputation** — Performance tracking and reputation-based vote weighting
- **Organization Memory** — Institutional knowledge preservation across sessions
- **Workflow Management** — Templated and custom workflow execution engine
- **Organization Learning** — Continuous improvement through pattern analysis

## Architecture

```
              AI Autonomous Multi Agent Collaboration Engine

                         │
        ┌────────────────┼────────────────┐
        │                │                │
 Communication     Coordination      Consensus
    Layer             Layer            Layer
        │                │                │
 Message Bus      Task Manager     Decision Engine
        │                │                │
        └────────────────┼────────────────┘
                         │
              Agent Organization Memory
```

## Organization Structure

```
                 AI CIO Agent
                      │
 ┌────────────┬───────┼────────┬──────────┐
 │            │       │        │          │
Research   Strategy  Risk   Portfolio  Execution
 Agent      Agent   Agent    Agent      Agent
                      │
              Learning Agent
```

## Core Modules

| Module | Class | Description |
|--------|-------|-------------|
| `message.py` | `AgentMessage`, `AgentIdentity`, `MessageProtocol` | Structured messaging protocol with validation |
| `communication.py` | `AgentCommunicationBus` | Centralized message routing, broadcast, threading |
| `delegation.py` | `TaskDelegationEngine` | Capability-based task assignment with 5 strategies |
| `coordinator.py` | `AgentCoordinator` | Investment committee workflow orchestration |
| `debate.py` | `MultiAgentDebateEngine` | 4-round debate simulation (Opening/Rebuttal/Cross/Closing) |
| `consensus.py` | `ConsensusDecisionEngine` | 5 voting methods, multi-score aggregation |
| `reputation.py` | `AgentReputationSystem` | 7 metrics, 5-tier reputation system |
| `memory.py` | `AgentOrganizationMemory` | Conversation, decision, outcome, and lesson storage |
| `workflow.py` | `AgentWorkflowEngine` | Template-based workflow execution with dependencies |
| `learning.py` | `OrganizationLearningEngine` | Organizational pattern analysis and improvement |
| `service.py` | `MultiAgentService` | Full collaboration loop orchestration |

## Communication Protocol

Each message contains:
- `sender` / `receiver` — Agent identities
- `task` — Task description
- `context` — Contextual data
- `priority` — CRITICAL / HIGH / MEDIUM / LOW

Communication rules enforce valid inter-agent channels (e.g., CIO can talk to all; Research talks to CIO, Strategy, Learning).

## Autonomous Multi Agent Loop

```
Market Event
      ↓
Research Agent
      ↓
Strategy Agent
      ↓
Risk Agent
      ↓
Portfolio Agent
      ↓
Investment Committee (Debate + Consensus)
      ↓
Execution Agent
      ↓
Learning Agent
      ↓
Organization Improvement
```

## Future Upgrade

- AI CIO Agent with autonomous decision authority
- Autonomous Investment Committee with rotating chairs
- Agent Market Simulation for strategy stress testing
- Self-Organized AI Team structure optimization
- Fully Autonomous Hedge Fund Organization
