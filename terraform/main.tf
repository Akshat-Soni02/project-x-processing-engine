resource "google_pubsub_topic" "arilo_llm_pipeline_topic" {
  name = "arilo-llm-pipeline-topic-${var.env}"
}

resource "google_pubsub_subscription" "arilo_llm_pipeline_stt_subscription" {
  name  = "arilo-llm-pipeline-stt-subscription-${var.env}"
  topic = google_pubsub_topic.arilo_llm_pipeline_topic.id

  ack_deadline_seconds = 300

  push_config {
    push_endpoint = "${var.llm_pipeline_base_url}/branch/subcription/stt"
    attributes = {
      x-goog-version = "v1"
    }
  }

  retry_policy {
    minimum_backoff = "1s"
    maximum_backoff = "3s"
  }
}

resource "google_pubsub_subscription" "arilo_llm_pipeline_smart_subscription" {
  name  = "arilo-llm-pipeline-smart-subscription-${var.env}"
  topic = google_pubsub_topic.arilo_llm_pipeline_topic.id

  ack_deadline_seconds = 300

  push_config {
    push_endpoint = "${var.llm_pipeline_base_url}/branch/subcription/smart"
    attributes = {
      x-goog-version = "v1"
    }
  }

  retry_policy {
    minimum_backoff = "1s"
    maximum_backoff = "3s"
  }
}

resource "google_sql_database_instance" "arilo_postgres" {
  name             = "arilo-postgres-${var.env}"
  database_version = "POSTGRES_15"
  region           = var.region

  deletion_protection = var.env == "prod" ? true : false

  settings {
    tier = var.db_tier
    database_flags {
      name  = "cloudsql.enable_google_ml_integration"
      value = "on"
    }
  }
}

resource "google_sql_database" "arilo_postgres" {
  name     = "arilo_postgres"
  instance = google_sql_database_instance.arilo_postgres.name
}

resource "google_sql_user" "arilo_postgres" {
  name     = "arilo_postgres"
  instance = google_sql_database_instance.arilo_postgres.name 
  password = var.db_password
}