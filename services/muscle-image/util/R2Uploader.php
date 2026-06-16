<?php
require_once __DIR__ . '/../vendor/autoload.php';
use Aws\S3\S3Client;
use Aws\Exception\AwsException;

class R2Uploader {
    private $s3Client;
    private $bucket;
    private $publicUrl;
    
    public function __construct() {
        $this->bucket = getenv('R2_BUCKET') ?: 'athleta-muscle-images';
        $accountId = getenv('R2_ACCOUNT_ID');
        $this->publicUrl = getenv('R2_PUBLIC_URL'); // e.g., https://pub-xxx.r2.dev
        
        if (!$accountId) {
            throw new Exception('R2_ACCOUNT_ID environment variable is required');
        }
        
        if (!$this->publicUrl) {
            throw new Exception('R2_PUBLIC_URL environment variable is required');
        }
        
        // R2 uses S3-compatible API with custom endpoint
        $this->s3Client = new S3Client([
            'version' => 'latest',
            'region' => 'auto', // R2 uses 'auto' for region
            'endpoint' => "https://{$accountId}.r2.cloudflarestorage.com",
            'credentials' => [
                'key'    => getenv('R2_ACCESS_KEY_ID'),
                'secret' => getenv('R2_SECRET_ACCESS_KEY'),
            ],
            // Important for R2
            'use_path_style_endpoint' => false,
        ]);
    }
    
    /**
     * Public R2 URL for an object key (no existence check).
     */
    public function urlFor($key) {
        return "{$this->publicUrl}/{$key}";
    }

    /**
     * Whether an object already exists in the bucket. Used to dedupe renders:
     * if the content-addressed key is already present we skip regeneration.
     */
    public function objectExists($key) {
        try {
            $this->s3Client->headObject([
                'Bucket' => $this->bucket,
                'Key'    => $key,
            ]);
            return true;
        } catch (AwsException $e) {
            if ($e->getStatusCode() === 404 || $e->getAwsErrorCode() === 'NotFound') {
                return false;
            }
            throw $e;
        }
    }

    public function uploadImage($imageResource, $key) {
        // Save to temp file
        $tempFile = tempnam(sys_get_temp_dir(), 'muscle_');
        imagepng($imageResource, $tempFile);
        
        try {
            $result = $this->s3Client->putObject([
                'Bucket' => $this->bucket,
                'Key'    => $key,
                'Body'   => fopen($tempFile, 'rb'),
                'ContentType' => 'image/png',
                // R2 doesn't use ACL, uses bucket-level public access
            ]);
            
            unlink($tempFile);
            
            // Return public URL (R2 public domain or custom domain)
            return "{$this->publicUrl}/{$key}";
        } catch (AwsException $e) {
            unlink($tempFile);
            error_log("R2 upload failed: " . $e->getMessage());
            throw $e;
        }
    }
}

