# Minimal GCP footprint for the pipeline: one landing bucket, three BigQuery
# datasets (raw / staging / analytics) and a least-privilege service account.
# Fits the BigQuery free tier for this data volume.

terraform {
  required_version = ">= 1.6"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

resource "google_project_service" "apis" {
  for_each           = toset(["bigquery.googleapis.com", "storage.googleapis.com", "iam.googleapis.com"])
  service            = each.value
  disable_on_destroy = false
}

resource "google_storage_bucket" "landing" {
  name                        = "${var.project_id}-tariff-landing"
  location                    = var.location
  uniform_bucket_level_access = true
  force_destroy               = true

  lifecycle_rule {
    condition { age = 90 }
    action { type = "Delete" }
  }

  depends_on = [google_project_service.apis]
}

resource "google_bigquery_dataset" "layers" {
  for_each                   = toset(["raw", "staging", "analytics"])
  dataset_id                 = each.value
  location                   = var.location
  delete_contents_on_destroy = true
  labels                     = { project = "indexed-tariffs", layer = each.value }

  depends_on = [google_project_service.apis]
}

resource "google_service_account" "pipeline" {
  account_id   = "tariff-pipeline"
  display_name = "Indexed tariffs ELT pipeline"
}

resource "google_project_iam_member" "bq_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.pipeline.email}"
}

resource "google_bigquery_dataset_iam_member" "editor" {
  for_each   = google_bigquery_dataset.layers
  dataset_id = each.value.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.pipeline.email}"
}

resource "google_storage_bucket_iam_member" "landing_rw" {
  bucket = google_storage_bucket.landing.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.pipeline.email}"
}
