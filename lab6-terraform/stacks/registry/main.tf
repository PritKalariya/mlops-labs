# Registry stack: the image repository. Separate state from serving, so an image
# can be pushed between the two applies without -target.
locals {
  project  = "boston-resilience-twin"
  location = "us-east1"
  labels   = { purpose = "lab6" }
}

provider "google" {
  project = local.project
  region  = local.location
}

module "registry" {
  source = "../../modules/registry"

  project       = local.project
  location      = local.location
  repository_id = "lab6"
  labels        = local.labels
}

output "image_base" {
  description = "Push images under this path; the forecast image is <image_base>/forecast."
  value       = module.registry.image_base
}
