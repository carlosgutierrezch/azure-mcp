param (
    [string]$imageName = "my-python-agent",
    [string]$imageTag = "latest",
    [string]$envFile = ".env"
)

# Check if Docker is installed
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Docker is not installed or not available in PATH."
    exit 1
}

# Check if the image exists
$imageExists = docker images -q "${imageName}:${imageTag}"
if (-not $imageExists) {
    Write-Host "❌ Docker image '${imageName}:${imageTag}' not found. Please build it first."
    exit 1
}

# Run the Docker container
Write-Host "🚀 Running Docker container from image '${imageName}:${imageTag}'..."
docker run -it `
    --env-file $envFile `
    -v "${PWD}:/app" `
    "${imageName}:${imageTag}"
    
# docker run --rm `
#     --env-file $envFile `
#     -v "${PWD}:/app" `
#     "${imageName}:${imageTag}"

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Docker container failed to run."
    exit 1
}

Write-Host "✅ Docker container ran successfully."
