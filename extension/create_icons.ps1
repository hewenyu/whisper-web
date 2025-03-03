# PowerShell script to create simple icon files for the Whisper Web extension

# Ensure the icons directory exists
$iconsDir = Join-Path $PSScriptRoot "icons"
if (-not (Test-Path $iconsDir)) {
    New-Item -ItemType Directory -Path $iconsDir | Out-Null
    Write-Host "Created icons directory: $iconsDir"
}

# Function to create a simple colored square icon
function Create-SimpleIcon {
    param (
        [int]$size,
        [string]$outputPath
    )
    
    # Create a new bitmap
    Add-Type -AssemblyName System.Drawing
    $bitmap = New-Object System.Drawing.Bitmap($size, $size)
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    
    # Fill with blue background
    $blue = [System.Drawing.Color]::FromArgb(52, 152, 219) # #3498db
    $brush = New-Object System.Drawing.SolidBrush($blue)
    $graphics.FillRectangle($brush, 0, 0, $size, $size)
    
    # Save the bitmap
    $bitmap.Save($outputPath, [System.Drawing.Imaging.ImageFormat]::Png)
    $bitmap.Dispose()
    $graphics.Dispose()
    
    Write-Host "Created icon: $outputPath"
}

# Create icons of different sizes
$icon16Path = Join-Path $iconsDir "icon16.png"
$icon48Path = Join-Path $iconsDir "icon48.png"
$icon128Path = Join-Path $iconsDir "icon128.png"

Create-SimpleIcon -size 16 -outputPath $icon16Path
Create-SimpleIcon -size 48 -outputPath $icon48Path
Create-SimpleIcon -size 128 -outputPath $icon128Path

Write-Host "All icons created successfully!" 