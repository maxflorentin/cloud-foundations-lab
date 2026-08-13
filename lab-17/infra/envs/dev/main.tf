module "landing" {
  source         = "../../modules/zona-lake"
  nombre         = "landing"
  entorno        = var.entorno
  versioning     = false
  retencion_dias = 30
}

module "raw" {
  source         = "../../modules/zona-lake"
  nombre         = "raw"
  entorno        = var.entorno
  versioning     = true
  retencion_dias = 0
}

module "curated" {
  source         = "../../modules/zona-lake"
  nombre         = "curated"
  entorno        = var.entorno
  versioning     = true
  retencion_dias = 0
}

module "consumer" {
  source         = "../../modules/zona-lake"
  nombre         = "consumer"
  entorno        = var.entorno
  versioning     = false
  retencion_dias = 0
}

output "buckets" {
  value = {
    landing  = module.landing.bucket_name
    raw      = module.raw.bucket_name
    curated  = module.curated.bucket_name
    consumer = module.consumer.bucket_name
  }
}
