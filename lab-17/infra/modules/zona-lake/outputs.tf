output "bucket_name" {
  description = "Nombre del bucket S3 creado"
  value       = aws_s3_bucket.zona.id
}

output "bucket_arn" {
  description = "ARN del bucket"
  value       = aws_s3_bucket.zona.arn
}
