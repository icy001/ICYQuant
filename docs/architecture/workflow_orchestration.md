# Workflow Orchestration Framework


## Workflow Execution


```
Workflow Definition

        |

        v

Task DAG

        |

        v

Execution Engine

        |

        v

State Machine

        |

        v

Result


```


## Example Trading Workflow


```
Signal

 ↓

Risk Check

 ↓

Order

 ↓

Execution

 ↓

Settlement

```


## Recovery


```
Failure

 ↓

Retry

 ↓

Compensation

 ↓

Rollback


```