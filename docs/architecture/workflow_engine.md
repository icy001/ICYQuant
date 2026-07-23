# Workflow Engine

```text

            Workflow Engine

                  │

                  ▼

        Workflow Definition

                  │

                  ▼

        Workflow Instance

                  │

                  ▼

           Step Executor

                  │

    ┌───────────┼───────────┐

    ▼           ▼           ▼

 Research      Trading      Risk

                  │

                  ▼

        Saga Coordinator

                  │

                  ▼

    Compensation Handler

                  │

                  ▼

    Long Running Transaction

```