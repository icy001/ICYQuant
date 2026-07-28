# Model Serving Infrastructure


## Responsibility

Provides:

- Prediction API
- Model Deployment
- Inference
- Monitoring
- Prediction Logging


## Architecture


Model Training

↓

Model Registry

↓

Serving

↓

Prediction

↓

Signal


## Future Upgrade

Production Features:

- FastAPI Serving Layer
- Kubernetes Deployment
- GPU Inference
- Feature Online Store
- Model Rollback
- Canary Deployment
- Real-Time Monitoring
