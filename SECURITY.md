# Disney Park Wait Times - Firebase Integration

## Setup Instructions

### 1. Environment Variables Setup

This project requires Firebase credentials that should **never be committed to git**. Follow these steps to set them up securely:

#### Option A: Using DigitalOcean CLI (Recommended for deployment)

```bash
# Set environment variables for DigitalOcean Functions
doctl serverless activations list  # Verify you're logged in

# Set your Firebase project ID
export FIREBASE_PROJECT_ID="your-firebase-project-id"

# Set your Firebase service account key (get from Firebase Console)
export FIREBASE_SERVICE_ACCOUNT_KEY='{"type": "service_account","project_id": "your-project-id",...}'

# Deploy with environment variables
doctl serverless deploy .
```

#### Option B: Using .env file (For local development)

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` with your actual credentials:
   ```
   FIREBASE_PROJECT_ID=your-actual-project-id
   FIREBASE_SERVICE_ACCOUNT_KEY={"type": "service_account",...}
   ```

### 2. Getting Firebase Credentials

1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Select your project
3. Go to Project Settings > Service Accounts
4. Click "Generate new private key"
5. Copy the entire JSON content for `FIREBASE_SERVICE_ACCOUNT_KEY`

### 3. Security Notes

- ✅ The `project.yml` now uses placeholders: `${FIREBASE_PROJECT_ID}`
- ✅ Actual credentials should be set as environment variables
- ✅ The `.gitignore` prevents accidental commits of sensitive files
- ⚠️ Never commit actual credentials to git
- ⚠️ Rotate credentials if accidentally exposed

### 4. Deployment

```bash
# Deploy to DigitalOcean Functions
doctl serverless deploy .

# Test the function
doctl serverless functions invoke parkmaster/refresh-waits
```

## Features

- ✅ Batch writes to Firestore (reduces daily write usage)
- ✅ OAuth2 authentication with service accounts
- ✅ Secure credential management
- ✅ Disney park wait times from 4 parks (126+ rides)
- ✅ Scheduled execution every 5 minutes
