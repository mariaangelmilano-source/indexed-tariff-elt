output "landing_bucket" {
  value = google_storage_bucket.landing.name
}

output "service_account_email" {
  value = google_service_account.pipeline.email
}

output "datasets" {
  value = [for d in google_bigquery_dataset.layers : d.dataset_id]
}
