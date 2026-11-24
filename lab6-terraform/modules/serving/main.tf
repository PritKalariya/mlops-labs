locals {
  ready_path = "/health/ready"
  live_path  = "/health/live"
  port       = 8080

  # Region subset for the uptime check: three US locations keep the execution count low.
  uptime_regions = ["USA_OREGON", "USA_IOWA", "USA_VIRGINIA"]

  # Service agent that sends the uptime check's OIDC-authenticated requests.
  monitoring_agent = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-monitoring-notification.iam.gserviceaccount.com"
}

data "google_project" "current" {
  project_id = var.project
}

# Runtime identity. No project roles are granted: the service reads nothing from GCP.
resource "google_service_account" "runtime" {
  project      = var.project
  account_id   = var.service_account_id
  display_name = "${var.name} Cloud Run runtime"
}

resource "google_cloud_run_v2_service" "this" {
  project  = var.project
  name     = var.name
  location = var.location
  labels   = var.labels

  # Destroy must work for a lab that is torn down at the end.
  deletion_protection = false

  template {
    service_account                  = google_service_account.runtime.email
    max_instance_request_concurrency = var.concurrency

    scaling {
      min_instance_count = var.min_instances
      max_instance_count = var.max_instances
    }

    containers {
      image = var.image

      ports {
        container_port = local.port
      }

      resources {
        # Request-based billing: CPU is allocated only while a request is being handled.
        # The provider default is always-allocated, which bills for the whole instance lifetime.
        cpu_idle = true

        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }

      startup_probe {
        period_seconds    = 2
        timeout_seconds   = 1
        failure_threshold = 30
        http_get {
          path = local.ready_path
          port = local.port
        }
      }

      liveness_probe {
        period_seconds    = 10
        timeout_seconds   = 1
        failure_threshold = 3
        http_get {
          path = local.live_path
          port = local.port
        }
      }
    }
  }

  lifecycle {
    # Ownership split: Terraform owns the service's shape; `gcloud run deploy`
    # (the release tool) owns which image runs and where traffic goes.
    ignore_changes = [
      # The image changes on every release. The var.image digest only seeds the first revision.
      template[0].containers[0].image,
      # Traffic is split between revisions by the release tool during canary and rollback.
      traffic,
      # `gcloud run deploy` stamps these two fields on every release. They carry no
      # setting, so they are not part of the shape Terraform owns.
      client,
      client_version,
    ]

    precondition {
      condition     = var.min_instances == 0 || var.allow_warm
      error_message = "min_instances is ${var.min_instances}, which keeps instances running and billing while idle. Set min_instances = 0, or set allow_warm = true to accept the cost."
    }
  }
}

# The Monitoring service agent may call this one service, and nothing else.
resource "google_cloud_run_v2_service_iam_member" "monitoring_invoker" {
  project  = var.project
  location = var.location
  name     = google_cloud_run_v2_service.this.name
  role     = "roles/run.invoker"
  member   = local.monitoring_agent

  # The Monitoring service agent does not exist until the first OIDC uptime check is
  # created, so the binding must come after it. Until the binding lands, the check
  # gets 403 responses, which is harmless because the alert policy is created last.
  depends_on = [google_monitoring_uptime_check_config.ready]
}

resource "google_cloud_run_v2_service_iam_member" "extra_invoker" {
  for_each = toset(var.invoker_members)

  project  = var.project
  location = var.location
  name     = google_cloud_run_v2_service.this.name
  role     = "roles/run.invoker"
  member   = each.value
}

resource "google_monitoring_uptime_check_config" "ready" {
  project          = var.project
  display_name     = "${var.name}-ready"
  period           = "60s"
  timeout          = "10s"
  selected_regions = local.uptime_regions
  user_labels      = var.labels

  # The API reports these as defaults on a Cloud Run check; stating them keeps plans clean.
  log_check_failures = false

  http_check {
    mask_headers   = false
    validate_ssl   = false
    path           = var.uptime_path
    port           = 443
    use_ssl        = true
    request_method = "GET"

    service_agent_authentication {
      type = "OIDC_TOKEN"
    }
  }

  # Service agent (OIDC) authentication is only accepted for Cloud Run resources,
  # not for an arbitrary uptime_url host.
  monitored_resource {
    type = "cloud_run_revision"
    labels = {
      project_id   = var.project
      service_name = google_cloud_run_v2_service.this.name
      location     = var.location
    }
  }

  lifecycle {
    # The API returns these two label keys as null for a service-level Cloud Run check.
    # Without this, every plan wants to replace the check.
    ignore_changes = [
      monitored_resource[0].labels["configuration_name"],
      monitored_resource[0].labels["revision_name"],
    ]

    # The alert policy references this check, so a replacement must create the new
    # check (the id has a random suffix) and repoint the policy before the old one goes.
    create_before_destroy = true
  }
}

resource "google_monitoring_notification_channel" "email" {
  project      = var.project
  display_name = "${var.name}-email"
  type         = "email"
  user_labels  = var.labels

  labels = {
    email_address = var.alert_email
  }
}

resource "google_monitoring_alert_policy" "uptime" {
  project      = var.project
  display_name = "${var.name}-uptime-failing"
  combiner     = "OR"
  user_labels  = var.labels

  notification_channels = [google_monitoring_notification_channel.email.id]

  # Created after the invoker binding so the first check results are not counted as failures.
  depends_on = [google_cloud_run_v2_service_iam_member.monitoring_invoker]

  conditions {
    display_name = "Uptime check failing from more than one region"

    condition_threshold {
      filter          = "metric.type=\"monitoring.googleapis.com/uptime_check/check_passed\" AND metric.label.check_id=\"${google_monitoring_uptime_check_config.ready.uptime_check_id}\" AND resource.type=\"${google_monitoring_uptime_check_config.ready.monitored_resource[0].type}\""
      comparison      = "COMPARISON_GT"
      threshold_value = 1
      duration        = "60s"

      aggregations {
        alignment_period     = "60s"
        per_series_aligner   = "ALIGN_NEXT_OLDER"
        cross_series_reducer = "REDUCE_COUNT_FALSE"
        group_by_fields      = ["metric.label.check_id"]
      }

      trigger {
        count = 1
      }
    }
  }

  documentation {
    mime_type = "text/markdown"
    content   = "The readiness path of ${var.name} failed its uptime check from more than one region."
  }
}
