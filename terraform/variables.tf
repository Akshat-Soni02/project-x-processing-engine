variable "project_id" {
  description = "The GCP project ID"
  type        = string
}

variable "env" {
  description = "dev or prod"
  type        = string
}

variable "region" {
  default = "us-central1"
}

variable "llm_pipeline_base_url" {
  description = "The base URL for the FastAPI push endpoints"
  type        = string
}

variable "db_tier" {
  description = "Machine type for the database"
  type        = string
}

variable "db_password" {
  description = "Password for the database user"
  type        = string
  sensitive   = true
}