variable "project" {
  description = "GCP project id that owns the repository."
  type        = string
}

variable "location" {
  description = "Region of the repository, for example us-east1."
  type        = string
}

variable "repository_id" {
  description = "Name of the Docker repository."
  type        = string
}

variable "labels" {
  description = "Labels applied to the repository."
  type        = map(string)
  default     = {}
}

variable "keep_count" {
  description = "Number of most recent versions the cleanup policy always keeps."
  type        = number
  default     = 5

  validation {
    condition     = var.keep_count >= 1
    error_message = "keep_count must be at least 1, otherwise the Keep policy protects nothing. Set it to 1 or more."
  }
}

variable "untagged_older_than" {
  description = "Untagged versions older than this are deleted, as a duration in seconds (86400s is one day)."
  type        = string
  default     = "86400s"

  validation {
    condition     = can(regex("^[0-9]+s$", var.untagged_older_than))
    error_message = "untagged_older_than must be a number of seconds such as 86400s. Use that form."
  }
}
