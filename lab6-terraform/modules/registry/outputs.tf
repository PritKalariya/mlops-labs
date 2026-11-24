output "repository_id" {
  description = "Repository name."
  value       = google_artifact_registry_repository.this.repository_id
}

output "image_base" {
  description = "Path to push images under, without an image name or tag."
  value       = "${var.location}-docker.pkg.dev/${var.project}/${google_artifact_registry_repository.this.repository_id}"
}
