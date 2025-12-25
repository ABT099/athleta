# Cloudflare R2 Setup for Muscle Image Service

## Environment Variables

The muscle-image service requires the following environment variables for R2 storage:

```env
R2_ACCOUNT_ID=your_cloudflare_account_id
R2_ACCESS_KEY_ID=your_r2_access_key
R2_SECRET_ACCESS_KEY=your_r2_secret_key
R2_BUCKET=athleta-muscle-images
R2_PUBLIC_URL=https://pub-xxxxx.r2.dev
```

## Getting R2 Credentials

1. **Get Account ID**:
   - Log in to Cloudflare Dashboard
   - Go to any page (e.g., Overview)
   - Account ID is shown in the right sidebar

2. **Create R2 Bucket**:
   - Go to R2 → Create Bucket
   - Name: `athleta-muscle-images`
   - Region: Auto (R2 distributes globally)

3. **Enable Public Access**:
   - Go to bucket Settings → Public Access
   - Enable "Allow Access"
   - Note the public URL: `https://pub-xxxxx.r2.dev`
   - Or configure custom domain (e.g., `images.athleta.com`)

4. **Create API Token**:
   - Go to R2 → Manage R2 API Tokens
   - Click "Create API Token"
   - Name: `muscle-image-service`
   - Permissions: "Object Read & Write"
   - Copy: Access Key ID and Secret Access Key

## Docker Compose Configuration

Add these to your `.env` file or docker-compose environment:

```env
R2_ACCOUNT_ID=your_account_id_here
R2_ACCESS_KEY_ID=your_access_key_here
R2_SECRET_ACCESS_KEY=your_secret_key_here
R2_BUCKET=athleta-muscle-images
R2_PUBLIC_URL=https://pub-xxxxx.r2.dev
```

## Testing

After setup, test the endpoint:

```bash
curl -X POST http://localhost:8081/generateAndStore \
  -H "Content-Type: application/json" \
  -d '{
    "workoutDayId": 1,
    "primaryMuscleGroups": "chest,triceps",
    "secondaryMuscleGroups": "shoulders",
    "primaryColor": "255,89,94",
    "secondaryColor": "138,201,38"
  }'
```

Expected response:
```json
{
  "url": "https://pub-xxxxx.r2.dev/muscle-images/1.png"
}
```

