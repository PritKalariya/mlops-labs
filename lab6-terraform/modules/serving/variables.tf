variable "project" {
  description = "GCP project id."
  type        = string
}

variable "location" {
  description = "Cloud Run region, for example us-east1."
  type        = string
}

variable "name" {
  description = "Cloud Run service name. Monitoring resources are named from it."
  type        = string
  default     = "lab6-forecast"
}

variable "service_account_id" {
  description = "Account id of the runtime service account. It is given no roles."
  type        = string
  default     = "lab6-run"
}

variable "image" {
  description = "Container image used when the service is first created. Must be pinned by digest."
  type        = string

  validation {
    condition     = can(regex("^[^@\\s]+@sha256:[0-9a-f]{64}$", var.image))
    error_message = "image must be pinned by digest, as <registry>/<path>@sha256:<64 hex characters>. A tag can move; build_push.sh prints the digest reference to use."
  }
}

variable "labels" {
  description = "Labels applied to every resource that supports them. Must include purpose."
  type        = map(string)

  validation {
    condition     = contains(keys(var.labels), "purpose")
    error_message = "labels must include a purpose key, for example { purpose = \"lab6\" }, so every resource can be traced to its lab."
  }
}

variable "concurrency" {
  description = "Maximum concurrent requests per instance."
  type        = number
  default     = 10

  validation {
    condition     = var.concurrency >= 1 && var.concurrency <= 80
    error_message = "concurrency must be between 1 and 80. Pick a value in that range (the lab uses 10)."
  }
}

variable "min_instances" {
  description = "Instances kept warm. Must be 0 unless allow_warm is true."
  type        = number
  default     = 0
}

variable "allow_warm" {
  description = "Set to true to permit min_instances above 0, which bills while idle."
  type        = bool
  default     = false
}

variable "max_instances" {
  description = "Instance cap, which bounds cost."
  type        = number
  default     = 2

  validation {
    condition     = var.max_instances >= 1 && var.max_instances <= 3
    error_message = "max_instances must be between 1 and 3 to keep the cost bounded. Lower it, or change this rule in the module if a higher cap is intended."
  }
}

variable "uptime_path" {
  description = "Path the uptime check requests."
  type        = string
  default     = "/health/ready"
}

variable "alert_email" {
  description = "Address that receives the uptime alert."
  type        = string
}

variable "invoker_members" {
  description = "Extra IAM members allowed to call the service, for example user:someone@example.com. Public members are rejected."
  type        = list(string)
  default     = []

  validation {
    condition     = length(setintersection(var.invoker_members, ["allUsers", "allAuthenticatedUsers"])) == 0
    error_message = "invoker_members must not include allUsers or allAuthenticatedUsers: the service is private. Name the user, group or service account that needs access."
  }
}
