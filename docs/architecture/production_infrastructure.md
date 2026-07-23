# ICYQuant Production Infrastructure


## Deployment Architecture


            Global Load Balancer


                     │


                     ▼


          Kubernetes Cluster


                     │


    ┌────────────────┼────────────────┐


    ▼                ▼                ▼


 Agents          Trading          Data


    │                │                │


    ▼                ▼                ▼


Service Mesh    Execution HA    Storage HA


                     │


                     ▼


              Monitoring


                     │


                     ▼


          Disaster Recovery