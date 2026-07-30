terraform {
  required_version = ">= 1.5.0"

  required_providers {
    alicloud = {
      source  = "aliyun/alicloud"
      version = "~> 1.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.0"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.0"
    }
  }

  backend "oss" {
    bucket   = "icyquant-terraform-state"
    key      = "alicloud/production/terraform.tfstate"
    endpoint = "oss-cn-hangzhou.aliyuncs.com"
  }
}

provider "alicloud" {
  region           = var.region
  access_key       = var.access_key
  secret_key       = var.secret_key
}

provider "kubernetes" {
  host                   = module.ack.endpoint
  cluster_ca_certificate = module.ack.cluster_ca_certificate
}

provider "helm" {
  kubernetes {
    host                   = module.ack.endpoint
    cluster_ca_certificate = module.ack.cluster_ca_certificate
  }
}

variable "region" {
  description = "Alibaba Cloud region"
  type        = string
  default     = "cn-hangzhou"
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "production"
}

variable "cluster_name" {
  description = "ACK cluster name"
  type        = string
  default     = "icyquant-production"
}
