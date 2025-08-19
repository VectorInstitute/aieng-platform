terraform {
  backend "gcs" {
    bucket = var.tf_state_bucket
  }
}
