# Ledger Architecture

## Overview

The Ledger service manages financial transactions and maintains audit trails for all trading activities.

## Components

### LedgerEntry

Represents a single ledger entry with:
- entry_id: Unique identifier
- user_id: User identifier
- symbol: Instrument symbol (optional)
- ledger_type: CASH or POSITION
- direction: DEBIT or CREDIT
- amount: Transaction amount
- reference_id: Reference to source transaction
- timestamp: Transaction time

### LedgerService

Core service for recording and querying ledger entries.

### TradeToLedger

Transformer that converts TradeDTO to LedgerEntry objects.

### PositionRebuilder

Reconstructs position state from ledger entries.

## Flow

1. Trade occurs
2. TradeToLedger converts to Cash and Position entries
3. LedgerService records entries
4. PositionRebuilder can reconstruct positions from entries
