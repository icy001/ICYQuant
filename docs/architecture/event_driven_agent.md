# Event Driven Multi-Agent Platform

```text

                 Event Runtime

                      │

                      ▼

               Event Router

                      │

      ┌───────────────┼───────────────┐

      ▼               ▼               ▼

 Research        Trading         Risk

 Agent            Agent          Agent

      │               │               │

      └───────────────┼───────────────┘

                      ▼

                Event Store

                      │

          ┌───────────┼────────────┐

          ▼           ▼            ▼

     Replay      Event Stream    DLQ

```