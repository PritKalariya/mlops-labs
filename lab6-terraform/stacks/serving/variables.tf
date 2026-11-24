variable "image" {
  description = "Image digest reference for the first revision, printed by scripts/build_push.sh."
  type        = string
}

variable "alert_email" {
  description = "Address that receives the uptime alert. Set it in terraform.tfvars."
  type        = string
}

variable "uptime_path" {
  description = "Path the uptime check requests."
  type        = string
  default     = "/health/ready"
}

variable "max_instances" {
  description = "Instance cap (1 to 3)."
  type        = number
  default     = 2
}

variable "concurrency" {
  description = "Concurrent requests per instance (1 to 80)."
  type        = number
  default     = 10
}

variable "min_instances" {
  description = "Warm instances. Must stay 0 unless allow_warm is true."
  type        = number
  default     = 0
}

variable "allow_warm" {
  description = "Permit min_instances above 0."
  type        = bool
  default     = false
}

variable "invoker_members" {
  description = "Extra IAM members allowed to call the service. Public members are rejected."
  type        = list(string)
  default     = []
}
