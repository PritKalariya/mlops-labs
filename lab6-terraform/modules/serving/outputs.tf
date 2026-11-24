output "service_name" {
  description = "Cloud Run service name."
  value       = google_cloud_run_v2_service.this.name
}

output "service_url" {
  description = "Cloud Run service URL. Private: calls need an identity token."
  value       = google_cloud_run_v2_service.this.uri
}

output "runtime_service_account" {
  description = "Email of the runtime service account."
  value       = google_service_account.runtime.email
}

output "uptime_check_id" {
  description = "Id of the uptime check."
  value       = google_monitoring_uptime_check_config.ready.uptime_check_id
}

output "alert_policy_name" {
  description = "Full name of the alert policy."
  value       = google_monitoring_alert_policy.uptime.name
}
