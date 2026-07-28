# Distributed Scheduler Service


## Responsibility


Provides:


- Scheduled execution

- Automated workflows

- Batch processing

- Trading calendar tasks


## Flow


```
Scheduler
|
v
Job Queue
|
v
Worker
|
v
Service Execution
```


## Future Upgrade


Production Features:


- Cron Expression Parser

- Leader Election

- Kubernetes CronJob

- Persistent Scheduler Store

- Task Retry

- Calendar Service

- Time Zone Support
