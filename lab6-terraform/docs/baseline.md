# Baseline: the course lab run as written

Source: `raminmohammadi/MLOps`, path `Labs/Terraform_Labs/GCP/Lab1_Beginner/` (`README.md`, `main.tf`).
Course HEAD when run: `034eb50`. Last commit touching `Labs/Terraform_Labs`: `cebce84` (2025-01-27, "updated gcp terraform lab").
Run date: 2026-11-24. Terraform v1.17.2, Ubuntu 26.04.1 LTS, project `boston-resilience-twin`, stock region `us-central1` / zone `us-central1-a`.

## Changes made to the stock files

| Change | Stock | Used |
|---|---|---|
| Project id | `<YOUR_PROJECT_ID>` | `boston-resilience-twin` |
| VM name | `terraform-vm` | `lab6-baseline-vm` |
| Bucket name | `terraform-lab-bucket-unique-12345` | `boston-resilience-twin-lab6-baseline` |
| Label | none on the Part 1 VM; `environment`, `owner` from Part 3 | `purpose=lab6` added to the VM at every stage and to the bucket (Part 4) |
| Image (forced, see below) | `debian-cloud/debian-11` | `debian-cloud/debian-12` |
| `allow_stopping_for_update` (forced, see below) | absent | `true`, from the second Part 3 apply onward |

The README parts were followed in order: Part 1 file, init, plan, apply; Part 3 edit and apply; Part 4 bucket and apply; Part 5 destroy.
The repository `main.tf` is the end state of Parts 3 and 4 (VM with labels, 12 GB disk, bucket), but with `f1-micro` kept. It was used as the reference for those stages.

## Measurements

| Step | Plan counts (add, change, destroy) | Result | Wall time |
|---|---|---|---|
| `terraform init` | n/a | resolved `hashicorp/google` **v8.12.0** (no version constraint in the stock file, so it floats) | 3 s |
| Part 2 plan, debian-11 | 1, 0, 0 | plan succeeds | n/a |
| Part 2 apply, debian-11 | 1, 0, 0 | **fails**: `Error resolving image name 'debian-cloud/debian-11': Could not find image or family debian-cloud/debian-11` | 2 s |
| Part 2 apply, debian-12 | 1, 0, 0 | VM created, `f1-micro` accepted in `us-central1-a` | 30 s (create 28 s) |
| Part 3 plan | 0, 1, 0 | machine type shown as update in place (`f1-micro` -> `e2-micro`), disk `10 -> 12` | n/a |
| Part 3 apply, as written | 0, 1, 0 | **fails**: machine type change on a running instance requires `allow_stopping_for_update = true` | 24 s |
| Part 3 re-plan and apply with `allow_stopping_for_update = true` | 0, 1, 0 | in-place update; the instance is stopped and restarted by the provider; final plan shows no changes | 138 s (plan and apply) |
| Part 4 apply (bucket) | 1, 0, 0 | bucket created | 4 s (plan and apply) |
| Part 5 `terraform destroy` | 0, 0, 2 | VM and bucket destroyed | 115 s |

Machine-type change outcome: in place, not a replacement, but only after `allow_stopping_for_update = true` was set. The first Part 3 apply failed part-way: the disk resize to 12 GB had already been applied, while the label and machine-type changes had not, so the next plan still showed those two.

After destroy, `compute instances list`, `compute disks list` and `storage buckets list`, each filtered to `lab6`, printed nothing. The working directory, including its state, was then deleted.

## README steps that cannot be followed as written

1. **Debian 11 image is gone.** `debian-cloud/debian-11` does not resolve (no `debian-11` family or image in the `debian-cloud` project). Plan succeeds because the image is resolved at apply time; apply fails. `debian-cloud/debian-12` works.
2. **Part 3 apply fails.** Changing `machine_type` on a running VM needs `allow_stopping_for_update = true`, which the README never mentions.
3. **README line 113 has an unterminated string:** `zone         = "us-central1-a` is missing its closing quote, so the Part 3 block does not parse if copied.
4. **No `terraform {}` block.** The provider version floats; the run above resolved v8.12.0. No `.gitignore` covers state or `.terraform/`.
5. **Placeholder project id.** `main.tf` ships `project = "<YOUR_PROJECT_ID>"`; the README uses `your-project-id`.
6. **Bucket name mismatch and collision.** README Part 4 uses `terraform-lab-bucket-unique-name`, `main.tf` uses `terraform-lab-bucket-unique-12345`. Bucket names are global, so either is likely to collide.
7. **Service account key.** The README creates an Editor service account and downloads a JSON key. Not followed; the run used application default credentials from a user login.
8. **`f1-micro` described as free tier.** The README gives no cost warning for the VM or its disk while it exists; the instance was created in `us-central1-a` and ran until destroyed.
