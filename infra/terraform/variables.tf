variable "project_id" {
  description = "GCP project that will host the pipeline"
  type        = string
}

variable "region" {
  description = "Default region for regional resources"
  type        = string
  default     = "us-central1"
}

variable "location" {
  description = "BigQuery / GCS multi-region"
  type        = string
  default     = "US"
}
