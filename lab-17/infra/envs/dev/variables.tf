variable "minio_endpoint" {
  type        = string
  description = "URL del endpoint S3 (MinIO)"
}

variable "minio_access_key" {
  type        = string
  description = "Access key de MinIO"
  sensitive   = true
}

variable "minio_secret_key" {
  type        = string
  description = "Secret key de MinIO"
  sensitive   = true
}

variable "entorno" {
  type        = string
  description = "Nombre del entorno"
  default     = "dev"
}
