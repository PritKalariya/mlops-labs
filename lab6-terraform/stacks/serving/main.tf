# Serving stack: runtime service account, private Cloud Run service, uptime check, alert.
locals {
  project  = "boston-resilience-twin"
  location = "us-east1"
  labels   = { purpose = "lab6" }
}

provider "google" {
  project = local.project
  region  = local.location
}

module "serving" {
  source = "../../modules/serving"

  project         = local.project
  location        = local.location
  image           = var.image
  labels          = local.labels
  alert_email     = var.alert_email
  uptime_path     = var.uptime_path
  max_instances   = var.max_instances
  concurrency     = var.concurrency
  min_instances   = var.min_instances
  allow_warm      = var.allow_warm
  invoker_members = var.invoker_members
}

output "service_url" {
  description = "Private service URL: calls need an identity token."
  value       = module.serving.service_url
}

output "service_name" {
  value = module.serving.service_name
}

output "runtime_service_account" {
  value = module.serving.runtime_service_account
}

output "uptime_check_id" {
  value = module.serving.uptime_check_id
}
