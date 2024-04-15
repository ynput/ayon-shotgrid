# Capture the current directory
$CurrentDir = Get-Location

$FunctionName = $ARGS[0]
$arguments = @()
if ($ARGS.Length -gt 1) {
    $arguments = $ARGS[1..($ARGS.Length - 1)]
}

# Function to get addon version from ../package.py
function Get-AddonVersion {
    return Invoke-Expression -Command "python -c ""import os;import sys;content={};f=open(r'../package.py');exec(f.read(),content);f.close();print(content['version'])"""
}

$AddonVersion = Get-AddonVersion
$ServiceDir = $arguments | Where-Object { $_ -notmatch "-Service" }

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
    Write-Host "Usage: .\manage.ps1 [target] -Service [service-name]"
    Write-Host ""
    Write-Host "Runtime targets:"
    Write-Host "build        Build docker image."
    Write-Host "build-all    Build docker image for 'leecher', 'procesor' and 'transmitter'."
    Write-Host "clean        Remove local images."
    Write-Host "clean-build  Remove local images and build without docker cache."
    Write-Host "dev          Run a service locally"
    Write-Host "dist         Push docker image to docker hub."
    Write-Host "dist-all     Push docker image to docker hub for 'leecher', 'procesor' and 'transmitter'."
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
    docker build --no-cache --network=host -t $Image -f "$ServiceDir/Dockerfile" .
}
function build-all {
    "leecher", "processor", "transmitter" | ForEach-Object {
        write-host "Building $_"
        .\manage.ps1 "build" -Service $_
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
    $Image = Get-ServiceImage
    docker push $Image
}
function dist-all {
    "leecher", "processor", "transmitter" | ForEach-Object {
        write-host "Pushing $_"
        .\manage.ps1 "push" -Service $_
    }
}

# Main function
function main {
    if ($FunctionName -eq "build") {
        Write-Host "Building service $ServiceDir"
        build
    }
    elseif ($FunctionName -eq "build-all") {
        Write-Host "Building all services"
        build-all
    }
    elseif ($FunctionName -eq "clean") {
        Write-Host "Cleaning service $ServiceDir"
        clean
    }
    elseif ($FunctionName -eq "clean-build") {
        Write-Host "Cleaning and building service $ServiceDir"
        clean-build
    }
    elseif ($FunctionName -eq "clean-build-all") {
        Write-Host "Cleaning and building all services"
        clean-build-all
    }
    elseif ($FunctionName -eq "dev") {
        dev
    }
    elseif ($FunctionName -eq "push") {
        dist
    }
    elseif ($FunctionName -eq "push-all") {
        Write-Host "Pushing all services to docker hub"
        dist-all
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