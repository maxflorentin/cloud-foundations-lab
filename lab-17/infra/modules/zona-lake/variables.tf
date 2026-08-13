variable "nombre" {
  type        = string
  description = "Nombre de la zona del lake (landing, raw, curated, consumer)"
  validation {
    condition     = contains(["landing", "raw", "curated", "consumer"], var.nombre)
    error_message = "nombre debe ser landing, raw, curated o consumer"
  }
}

variable "entorno" {
  type        = string
  description = "Entorno de despliegue (dev, prod)"
  validation {
    condition     = contains(["dev", "prod"], var.entorno)
    error_message = "entorno debe ser dev o prod"
  }
}

variable "versioning" {
  type        = bool
  description = "Habilitar versionado de objetos"
  default     = false
}

variable "retencion_dias" {
  type        = number
  description = "Días de retención de objetos (0 = sin lifecycle)"
  default     = 0
  validation {
    condition     = var.retencion_dias >= 0
    error_message = "retencion_dias debe ser >= 0"
  }
}

variable "habilitar_lifecycle" {
  type        = bool
  description = "Crear aws_s3_bucket_lifecycle_configuration (false en MinIO — no soporta el waiter del provider)"
  default     = false
}

variable "lectores" {
  type        = list(string)
  description = "Lista de ARNs de usuarios IAM con acceso de lectura (vacía = sin política)"
  default     = []
}
