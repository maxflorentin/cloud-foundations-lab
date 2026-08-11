LOAD httpfs;
SET s3_endpoint          = 'localhost:{{PORT}}';
SET s3_access_key_id     = 'minioadmin';
SET s3_secret_access_key = 'minioadmin';
SET s3_use_ssl           = false;
SET s3_url_style         = 'path';
SET s3_region            = 'us-east-1';
