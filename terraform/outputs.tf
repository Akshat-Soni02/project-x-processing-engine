output "pubsub_topic_id" {
  value = google_pubsub_topic.arilo_llm_pipeline_topic.id
}

output "db_connection_name" {
  value = google_sql_database_instance.arilo_postgres.connection_name
}

output "db_public_ip" {
  value = google_sql_database_instance.arilo_postgres.public_ip_address
}