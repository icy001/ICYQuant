# Feature Store Engine


## Responsibility

Provides:

- Feature Definition
- Feature Registry
- Feature Versioning
- Online Serving
- Offline Storage
- Validation


## Architecture

```text
Raw Data

↓

Pipeline

↓

Feature Store

↓

Strategy / Model

```

## Future Upgrade

Production Features:

* Feast Integration
* Redis Online Store
* Data Lake Offline Store
* Feature Lineage
* Feature Monitoring
* Feature Drift Detection
* Automatic Feature Generation
