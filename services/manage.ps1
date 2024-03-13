# Capture the current directory
$CurrentDir = Get-Location

$FunctionName = $ARGS[0]
$arguments = @()
if ($ARGS.Length -gt 1) {
    $arguments = $ARGS[1..($ARGS.Length - 1)]
}

# Function to get addon version from ../version.py
function Get-AddonVersion {
    $versionLine = Get-Content -Path "../version.py" | Where-Object { $_ -match "__version__" }
    $version = $versionLine.Split(" ")[2].Trim('"')
    return $version
}

$AddonVersion = Get-AddonVersion
$ServiceDir = $arguments | Where-Object { $_ -notmatch "-Service" }
Write-Host "Image: "$ServiceDir

function EnsureServiceDir {
    if (-not $ServiceDir) {
        Write-Host "-----------------------------"
        Write-Host "! -Service name is required !"
        Write-Host "-----------------------------"
        Show-Help
        exit
    }
}
function Get-ServiceImage {
    EnsureServiceDir
    $Image = "ynput/ayon-shotgrid-$ServiceDir" + ":$AddonVersion"
    Write-Host "Image: "$Image
    return $Image
}

# Show help message with details on how to use this script
function Show-Help {
    Write-Host ""
    Write-Host "Ayon Shotgrid $AddonVersion Service Builder"
    Write-Host ""
    Write-Host "Usage: .\manage.ps1 [target] -SERVICE [service-name]"
    Write-Host ""
    Write-Host "Runtime targets:"
    Write-Host "build        Build docker image."
    Write-Host "build-all    Build docker image for 'leecher', 'procesor' and 'transmitter'."
    Write-Host "clean        Remove local images."
    Write-Host "clean-build  Remove local images and build without docker cache."
    Write-Host "dev          Run a service locally"
    Write-Host ""
    Write-Host "Passing -Service is required for any of the targets to work, possible services:"
    Write-Host ""
    Write-Host "  leecher - Fetch Shotgrid Events into AYON."
    Write-Host "  processor - Process 'shotgrid.event's in AYON."
    Write-Host "  transmitter - Push AYON events to Shotgrid."
    Write-Host ""
}

function build {
    $Image = Get-ServiceImage
    docker build --network=host -t $Image -f "$ServiceDir/Dockerfile" .
}
function build-all {
    "leecher", "processor", "transmitter" | ForEach-Object {
        .\manage.ps1 "build" -Service_dir $_
    }
}
function clean {
    $Image = Get-ServiceImage
    & docker rmi $Image
}
function clean-build {
    $Image = Get-ServiceImage
    .\manage.ps1 clean -Service $ServiceDir
    docker build --network=host --no-cache -t $Image -f "$ServiceDir/Dockerfile" .
}
function clean-build-all {
    "leecher", "processor", "transmitter" | ForEach-Object {
        .\manage.ps1 clean-build -Service $_
    }
}
function dev {
    EnsureServiceDir
    write-host "$CurrentDir/$ServiceDir"
    New-Item -Path "$CurrentDir/$ServiceDir" -ItemType SymbolicLink -Value "$CurrentDir/shotgrid_common/*"
    docker run --rm -u ayonuser -ti `
        -v "$CurrentDir/shotgrid_common:$CurrentDir/shotgrid_common:Z" `
        -v "$CurrentDir/$ServiceDir" + ":/service:Z" `
        --env-file "$CurrentDir/$ServiceDir/.env" `
        --env AYON_ADDON_NAME=shotgrid `
        --env AYON_ADDON_VERSION=$AddonVersion `
        --network=host $Image python -m $ServiceDir

    Remove-Item -Path "$CurrentDir/$ServiceDir" -Force
}
function shell {
    docker run --rm -u ayonuser -ti -v "$CurrentDir/$ServiceDir/$ServiceDir" + ":/service:Z" $Image /bin/sh
}
function dist {
    build
    # Publish the docker image to the registry
    docker push "$Image"
}


# Main function
function main {
    if ($FunctionName -eq "build") {
        build
    }
    elseif ($FunctionName -eq "build-all") {
        clean
    }
    elseif ($FunctionName -eq "clean") {
        dev
    }
    elseif ($FunctionName -eq "clean-build") {
        dist
    }
    elseif ($FunctionName -eq "clean-build-all") {
        bash
    }
    elseif ($FunctionName -eq "dev") {
        dev
    }
    elseif ($FunctionName -eq "shell") {
        shell
    }
    elseif ($FunctionName -eq $null) {
        Show-Help
    }
    else {
        Write-Host "Unknown function ""$FunctionName"""
    }
}

main