<#
.SYNOPSIS
  Helper script to manage Shotgrid Addon Services

.DESCRIPTION
  Handle docker builds and local development for the Shotgrid Addon Services.

.EXAMPLE

Show usage:
PS> .\manage.ps1

.EXAMPLE

Build the 'leecher' service:
PS> .\manage.ps1 build leecher

.EXAMPLE

Build all services:
PS> .\manage.ps1 build-all

#>

$script_dir = Split-Path -Path $MyInvocation.MyCommand.Definition -Parent
$repo_root = (Get-Item $script_dir).parent.FullName

$FunctionName=$ARGS[0]
$service = $ARGS[1]
$arguments=@()
if ($ARGS.Length -gt 1) {
    $arguments = $ARGS[1..($ARGS.Length - 1)]
}

$services = 'leecher','processor','transmitter'



$art = @"

                    ▄██▄
         ▄███▄ ▀██▄ ▀██▀ ▄██▀ ▄██▀▀▀██▄    ▀███▄      █▄
        ▄▄ ▀██▄  ▀██▄  ▄██▀ ██▀      ▀██▄  ▄  ▀██▄    ███
       ▄██▀  ██▄   ▀ ▄▄ ▀  ██         ▄██  ███  ▀██▄  ███
      ▄██▀    ▀██▄   ██    ▀██▄      ▄██▀  ███    ▀██ ▀█▀
     ▄██▀      ▀██▄  ▀█      ▀██▄▄▄▄██▀    █▀      ▀██▄

     ·  · - =[ by YNPUT ]:[ http://ayon.ynput.io ]= - ·  ·

"@


function Get-AsciiArt() {
    Write-Host $art -ForegroundColor DarkGreen
}

function Exit-WithCode($exitcode) {
   # Only exit this host process if it's a child of another PowerShell parent process...
   $parentPID = (Get-CimInstance -ClassName Win32_Process -Filter "ProcessId=$PID" | Select-Object -Property ParentProcessId).ParentProcessId
   $parentProcName = (Get-CimInstance -ClassName Win32_Process -Filter "ProcessId=$parentPID" | Select-Object -Property Name).Name
   if ('powershell.exe' -eq $parentProcName) { $host.SetShouldExit($exitcode) }

   exit $exitcode
}

$version_file = Get-Content -Path "$($repo_root)\version.py"
$result = [regex]::Matches($version_file, '__version__ = "(?<version>\d+\.\d+.\d+.*)"')
$addon_version = $result[0].Groups['version'].Value
if (-not $addon_version) {
  Write-Host "!!! Cannot determine addon version."
  Exit-WithCode 1
}

$image = "ynput/ayon-shotgrid-$($service):$($addon_version)"


function Show-Usage() {
    $usage = @'
    Usage: ./manage.ps1 [command] [service]

    Possible services:

        leecher      Fetch Shotgrid Events into AYON
        processor    Process 'shotgrid.event's in AYON
        transmitter  Push AYON events to Shotgrid

    Commands:

        build        Build docker image
        build-all    Build docker image for 'leecher', 'procesor' and 'transmitter'
        clean        Remove local images
        clean-build  Remove local images and build without docker cache
        dev          Run a service locally

'@

    Get-AsciiArt
    Write-Host "Ayon Shotgrid Service Builder v$addon_version" -ForegroundColor DarkGreen
    Write-Host $usage -ForegroundColor Gray
}

function New-TemporaryDirectory {
    $parent = [System.IO.Path]::GetTempPath()
    [string] $name = [System.Guid]::NewGuid()
    New-Item -ItemType Directory -Path (Join-Path $parent $name)
}

function Invoke-Build {
    param ([switch]$All, [switch]$NoCache)

    $cache = ""
    if ($NoCache) {
        Write-Host ">>> Building $service without cache ..."
        $cache = "--no-cache "
    }

    if ($All) {
        foreach ($service in $services) {
            Write-Host ">>> Building $service ..."
            & docker build -t "ynput/ayon-shotgrid-$($service):$($addon_version)" -f "$($repo_root)\services\$($service)\Dockerfile" $repo_root\services
        }
    } else {
        Write-Host ">>> Building $service ..."
        & docker build --network=host -t $image -f $repo_root\services\$service\Dockerfile $repo_root\services
    }
    Write-Host ">>> Done."
}


function Clear-Images {
    Write-Host ">>> Looking for $image ..."
    if ($null -ne (docker images -a --format '{{print .Tag | print ":" | print .Repository}}' | Select-String -Pattern $image)) {
        Write-Host ">>> Removing $image ..."
        & docker rmi $image
    }    
}

function Start-Dev {
    Write-Host ">>> Starting $service ..."

    <#

    $IsAdministrator = ([Security.Principal.WindowsPrincipal]::new(
        ($id = [Security.Principal.WindowsIdentity]::GetCurrent())
    )).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    $id.dispose(); remove-variable id

    if (-not $IsAdministrator) {
        Write-Host "!!! Warning: This must be run from a PowerShell terminal with Administrator privileges !!!" -ForegroundColor Yellow
        $confirmation = Read-Host "Running without them might not work. Are you sure you want to proceed [y/n]: "
        if ($confirmation -eq 'n') {
            Write-Host ">>> Aborting."
            Exit-WithCode 1
        }
    }

    Write-Host ">>> Creating symbolic link for shotgrid_common ..."
    $dir_path = "$($repo_root)\services\shotgrid_common"
    $target_dir = "$($repo_root)\services\$($service)"

    Get-ChildItem -Path $dir_path | ForEach-Object {
        Write-Host ">>> Creating symbolic link for $($_.Name) ..."
        $link_path = Join-Path -Path $target_dir -ChildPath $_.Name
        try {
            New-Item -ItemType SymbolicLink -Path $link_path -Target $_.FullName -ErrorAction Stop  | Out-Null
        }
        catch [System.IO.IOException] {
            Write-Warning ">>> Symbolic link for $($_.Name) already exists."
        }
        catch {
            Write-Warning ">>> Error creating symbolic link for $($_.Name): $_"
        }
    }
    #>

    $envFile = "$($repo_root)\services\$($service)\.env"
    if (Test-Path $envFile -PathType Leaf) {
        Write-Host ">>> Using $envFile as environment file."
    } else {
        Write-Warning ">>> No environment file found, you might be missing AYON_API_KEY..."
    }
    
    Write-Host "--- running image $image"
    & docker run --rm -ti -v $repo_root\services\shotgrid_common:/service/shotgrid_common -v "$($repo_root)\services\$($service):/service" --env-file $envFile --env AYON_ADDON_NAME=shotgrid --env AYON_ADDON_VERSION=$addon_version --attach=stdin --attach=stdout --attach=stderr --network=host $image python -m $service
}


function Main {
   

    if ($null -eq $FunctionName) {
        Show-Usage
        return
    }

    if ($services -notcontains $service) {
        Write-Host $FunctionName
        if ($FunctionName -ne "build-all") {
            Write-Host "Unknown service '$($service)' (possible values: $($services -join ', '))"
            Show-Usage
            return
        }
    }

    $FunctionName = $FunctionName.ToLower() -replace "\W"
    if ($FunctionName -eq "build") {
        Invoke-Build
    } elseif ($FunctionName -eq "buildall") {
        Invoke-Build -All
    } elseif ($FunctionName -eq "clean") {
        Clear-Images
    } elseif ($FunctionName -eq "cleanbuild") {
        Clear-Images
        Invoke-Build -NoCache
    } elseif ($FunctionName -eq "dev") {
        Start-Dev
    } else {
        Write-Host "Unknown command ""$FunctionName"""
        Show-Usage
    }
}

Main
