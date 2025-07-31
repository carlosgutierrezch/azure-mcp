param (
    [string]$imageName = "my-python-agent",
    [string]$imageTag = "latest"
)

# Check if Dockerfile exists
if (-Not (Test-Path -Path "./Dockerfile")) {
    Write-Host "❌ Dockerfile not found in the current directory."
    exit 1
}

# Build the Docker image with no cache
Write-Host "🚧 Building Docker image '${imageName}:${imageTag}' with --no-cache..."
docker build --no-cache -t "${imageName}:${imageTag}" .

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Docker build failed."
    exit 1
}

# Tag the image with 'latest'
Write-Host "🏷️ Tagging the image with 'latest'..."
docker tag "${imageName}:${imageTag}" "${imageName}:latest"

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Docker tag failed."
    exit 1
}

Write-Host "✅ Docker image '$imageName' built and tagged successfully."