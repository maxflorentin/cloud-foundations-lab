locals {
  bucket_name = "${var.entorno}-${var.nombre}"
}

resource "aws_s3_bucket" "zona" {
  bucket = local.bucket_name
}

resource "aws_s3_bucket_versioning" "zona" {
  bucket = aws_s3_bucket.zona.id

  versioning_configuration {
    status = var.versioning ? "Enabled" : "Suspended"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "zona" {
  count  = (var.habilitar_lifecycle && var.retencion_dias > 0) ? 1 : 0
  bucket = aws_s3_bucket.zona.id

  rule {
    id     = "expira-${var.retencion_dias}d"
    status = "Enabled"

    filter {}

    expiration {
      days = var.retencion_dias
    }
  }
}

resource "aws_s3_bucket_policy" "lectores" {
  count  = length(var.lectores) > 0 ? 1 : 0
  bucket = aws_s3_bucket.zona.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { AWS = var.lectores }
      Action    = ["s3:GetObject", "s3:ListBucket"]
      Resource  = [
        aws_s3_bucket.zona.arn,
        "${aws_s3_bucket.zona.arn}/*"
      ]
    }]
  })
}
