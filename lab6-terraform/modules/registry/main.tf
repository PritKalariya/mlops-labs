resource "google_artifact_registry_repository" "this" {
  project       = var.project
  location      = var.location
  repository_id = var.repository_id
  format        = "DOCKER"
  description   = "Container images for ${var.repository_id}"
  labels        = var.labels

  # The policies are enforced, not just reported.
  cleanup_policy_dry_run = false

  cleanup_policies {
    id     = "keep-${var.keep_count}-most-recent"
    action = "KEEP"
    most_recent_versions {
      keep_count = var.keep_count
    }
  }

  cleanup_policies {
    id     = "delete-untagged-after-1d"
    action = "DELETE"
    condition {
      tag_state  = "UNTAGGED"
      older_than = var.untagged_older_than
    }
  }
}
