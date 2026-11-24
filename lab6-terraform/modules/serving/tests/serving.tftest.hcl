# Plan-mode tests with a mocked provider: no credentials, no network, nothing created.
# Run from modules/serving with: terraform init -backend=false && terraform test

mock_provider "google" {}

override_data {
  target          = data.google_project.current
  override_during = plan
  values = {
    number = "123456789012"
  }
}

override_resource {
  target          = google_monitoring_uptime_check_config.ready
  override_during = plan
  values = {
    uptime_check_id = "lab6-forecast-ready-test"
  }
}

override_resource {
  target          = google_service_account.runtime
  override_during = plan
  values = {
    email = "lab6-run@example-project.iam.gserviceaccount.com"
  }
}

variables {
  project     = "example-project"
  location    = "us-east1"
  image       = "us-east1-docker.pkg.dev/example-project/lab6/forecast@sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
  labels      = { purpose = "lab6" }
  alert_email = "ops@example.com"
}

run "valid_plan_matches_the_lab_settings" {
  command = plan

  assert {
    condition     = google_cloud_run_v2_service.this.template[0].containers[0].startup_probe[0].http_get[0].path == "/health/ready"
    error_message = "startup probe must use /health/ready"
  }

  assert {
    condition = (
      google_cloud_run_v2_service.this.template[0].containers[0].startup_probe[0].period_seconds == 2 &&
      google_cloud_run_v2_service.this.template[0].containers[0].startup_probe[0].timeout_seconds == 1 &&
      google_cloud_run_v2_service.this.template[0].containers[0].startup_probe[0].failure_threshold == 30
    )
    error_message = "startup probe must be period 2s, timeout 1s, threshold 30"
  }

  assert {
    condition     = google_cloud_run_v2_service.this.template[0].containers[0].liveness_probe[0].http_get[0].path == "/health/live"
    error_message = "liveness probe must use /health/live"
  }

  assert {
    condition = (
      google_cloud_run_v2_service.this.template[0].containers[0].liveness_probe[0].period_seconds == 10 &&
      google_cloud_run_v2_service.this.template[0].containers[0].liveness_probe[0].timeout_seconds == 1 &&
      google_cloud_run_v2_service.this.template[0].containers[0].liveness_probe[0].failure_threshold == 3
    )
    error_message = "liveness probe must be period 10s, timeout 1s, threshold 3"
  }

  assert {
    condition     = google_cloud_run_v2_service.this.template[0].max_instance_request_concurrency == 10
    error_message = "concurrency must default to 10"
  }

  assert {
    condition = (
      google_cloud_run_v2_service.this.template[0].scaling[0].min_instance_count == 0 &&
      google_cloud_run_v2_service.this.template[0].scaling[0].max_instance_count == 2
    )
    error_message = "scaling must default to min 0, max 2"
  }

  assert {
    condition = (
      google_cloud_run_v2_service.this.template[0].containers[0].resources[0].limits["cpu"] == "1" &&
      google_cloud_run_v2_service.this.template[0].containers[0].resources[0].limits["memory"] == "512Mi" &&
      google_cloud_run_v2_service.this.template[0].containers[0].resources[0].cpu_idle == true &&
      google_cloud_run_v2_service.this.template[0].containers[0].ports[0].container_port == 8080
    )
    error_message = "must run with cpu 1, 512Mi, port 8080, request-based CPU"
  }

  assert {
    condition     = google_cloud_run_v2_service.this.labels["purpose"] == "lab6"
    error_message = "service must carry purpose=lab6"
  }

  assert {
    condition = (
      google_monitoring_uptime_check_config.ready.user_labels["purpose"] == "lab6" &&
      google_monitoring_notification_channel.email.user_labels["purpose"] == "lab6" &&
      google_monitoring_alert_policy.uptime.user_labels["purpose"] == "lab6"
    )
    error_message = "monitoring resources must carry purpose=lab6"
  }

  assert {
    condition     = google_cloud_run_v2_service.this.template[0].service_account == "lab6-run@example-project.iam.gserviceaccount.com"
    error_message = "service must run as the lab6-run service account"
  }

  assert {
    condition     = google_service_account.runtime.account_id == "lab6-run"
    error_message = "runtime service account id must be lab6-run"
  }

  assert {
    condition     = google_cloud_run_v2_service.this.deletion_protection == false
    error_message = "deletion_protection must be false so destroy works"
  }

  assert {
    condition = alltrue([
      for m in concat(
        [google_cloud_run_v2_service_iam_member.monitoring_invoker.member],
        [for r in values(google_cloud_run_v2_service_iam_member.extra_invoker) : r.member]
      ) : !contains(["allUsers", "allAuthenticatedUsers"], m)
    ])
    error_message = "no public invoker may exist"
  }

  assert {
    condition     = google_cloud_run_v2_service_iam_member.monitoring_invoker.member == "serviceAccount:service-123456789012@gcp-sa-monitoring-notification.iam.gserviceaccount.com"
    error_message = "only the Monitoring service agent gets invoker by default"
  }

  assert {
    condition     = google_monitoring_uptime_check_config.ready.http_check[0].path == "/health/ready"
    error_message = "uptime check must default to /health/ready"
  }

  assert {
    condition     = google_monitoring_uptime_check_config.ready.http_check[0].service_agent_authentication[0].type == "OIDC_TOKEN"
    error_message = "uptime check must authenticate with an OIDC token"
  }

  assert {
    condition     = google_monitoring_uptime_check_config.ready.period == "60s"
    error_message = "uptime check must run every 60s"
  }

  assert {
    condition     = google_monitoring_notification_channel.email.labels["email_address"] == "ops@example.com"
    error_message = "alert channel must email var.alert_email"
  }

  # The alert filter must select the series the uptime check really writes: same check id,
  # same monitored resource type, and a group-by that exists on that series.
  assert {
    condition = (
      strcontains(google_monitoring_alert_policy.uptime.conditions[0].condition_threshold[0].filter, "metric.label.check_id=\"lab6-forecast-ready-test\"") &&
      strcontains(google_monitoring_alert_policy.uptime.conditions[0].condition_threshold[0].filter, "resource.type=\"${google_monitoring_uptime_check_config.ready.monitored_resource[0].type}\"") &&
      !strcontains(google_monitoring_alert_policy.uptime.conditions[0].condition_threshold[0].filter, "uptime_url") &&
      google_monitoring_alert_policy.uptime.conditions[0].condition_threshold[0].aggregations[0].group_by_fields[0] == "metric.label.check_id"
    )
    error_message = "alert filter must match the uptime check's id and monitored resource type, and group by metric.label.check_id"
  }

  assert {
    condition     = google_monitoring_uptime_check_config.ready.monitored_resource[0].type == "cloud_run_revision"
    error_message = "service agent (OIDC) authentication requires a cloud_run_revision monitored resource"
  }

  assert {
    condition     = startswith(google_monitoring_uptime_check_config.ready.display_name, "lab6-") && startswith(google_monitoring_alert_policy.uptime.display_name, "lab6-") && startswith(google_monitoring_notification_channel.email.display_name, "lab6-")
    error_message = "monitoring resources must have display names starting lab6-"
  }
}

run "warm_instances_allowed_when_opted_in" {
  command = plan

  variables {
    min_instances = 1
    allow_warm    = true
  }

  assert {
    condition     = google_cloud_run_v2_service.this.template[0].scaling[0].min_instance_count == 1
    error_message = "min_instances must pass through when allow_warm is true"
  }
}

run "rejects_image_tag" {
  command = plan

  variables {
    image = "us-east1-docker.pkg.dev/example-project/lab6/forecast:latest"
  }

  expect_failures = [var.image]
}

run "rejects_max_instances_above_3" {
  command = plan

  variables {
    max_instances = 10
  }

  expect_failures = [var.max_instances]
}

run "rejects_concurrency_above_80" {
  command = plan

  variables {
    concurrency = 81
  }

  expect_failures = [var.concurrency]
}

run "rejects_warm_instances_without_opt_in" {
  command = plan

  variables {
    min_instances = 1
  }

  expect_failures = [google_cloud_run_v2_service.this]
}

run "rejects_labels_without_purpose" {
  command = plan

  variables {
    labels = { team = "ml" }
  }

  expect_failures = [var.labels]
}

run "rejects_public_invoker" {
  command = plan

  variables {
    invoker_members = ["allUsers"]
  }

  expect_failures = [var.invoker_members]
}
