# Receive first positional argument
$FunctionName=$ARGS[0]
$arguments=@()
if ($ARGS.Length -gt 1) {
    $arguments = $ARGS[1..($ARGS.Length - 1)]
}

$script_dir_rel = Split-Path -Path $MyInvocation.MyCommand.Definition -Parent
$script_dir = (Get-Item $script_dir_rel).FullName

$ADDON_VERSION = Invoke-Expression -Command "python -c ""import os;import sys;content={};f=open(r'$($script_dir)/../package.py');exec(f.read(),content);f.close();print(content['version'])"""

function Default-Func {
  Write-Host ""
  Write-Host "*************************"
  Write-Host "AYON shotgrid services tool"
  Write-Host "   Run shotgrid services"
  Write-Host "*************************"
  Write-Host ""
  Write-Host "Run service processes from terminal. It is recommended to use docker images for production."
  Write-Host ""
  Write-Host "Usage: .\Manage.ps1 [target]"
  Write-Host ""
  Write-Host "Optional arguments for service targets:"
  Write-Host "--variant [variant] (Define settings variant. default: 'production')"
  Write-Host ""
  Write-Host "Runtime targets:"
  Write-Host "  create-env    Install requirements to currently actie python (recommended to create venv)"
  Write-Host "  leecher       Start leecher of shotgrid events"
  Write-Host "  processor     Main processing logic"
  Write-Host "  transmitter   Transmit AYON events to shotgrid"
  Write-Host "  services      Start both leecher and processor (experimental)"
  Write-Host ""
}

function Install-Requirements {
  # TODO Install/verify venv is created
  & python -m pip install -e "$($script_dir)"
}

function Start-Leecher {
  & python "$($script_dir)\main.py" --service leecher @arguments
}

function Start-Processor {
  & python "$($script_dir)\main.py" --service processor @arguments
}

function Start-Transmitter {
  & python "$($script_dir)\main.py" --service transmitter @arguments
}

function Start-All {
  & python "$($script_dir)\main.py" --service all @arguments
}

function Load-Env {
  $env_path = "$($script_dir)/.env"
  if (Test-Path $env_path) {
    Get-Content $env_path | foreach {
      $name, $value = $_.split("=")
      if (-not([string]::IsNullOrWhiteSpace($name) -or $name.Contains("#"))) {
        Set-Content env:\$name $value
      }
    }
  }
}

function Activate-Venv {
  # Make sure venv is created
  $venv_path = "$($script_dir)\.venv"
  if (-not(Test-Path $venv_path)) {
    & python -m venv $venv_path
  }
  & "$($venv_path)\Scripts\activate.ps1"
}

function main {
  if ($null -eq $FunctionName) {
    Default-Func
    return
  }
  $FunctionName = $FunctionName.ToLower() -replace "\W"
  $env:AYON_ADDON_NAME = "shotgrid"
  $env:AYON_ADDON_VERSION = $ADDON_VERSION
  Load-Env
  Activate-Venv

  try {
    if ($FunctionName -eq "createenv") {
      Install-Requirements
    } elseif ($FunctionName -eq "leecher") {
      Start-Leecher
    } elseif ($FunctionName -eq "processor") {
      Start-Processor
    } elseif ($FunctionName -eq "transmitter") {
      Start-Transmitter
    } elseif ($FunctionName -eq "services") {
      Start-All
    } else {
      Write-Host "Unknown function ""$FunctionName"""
      Default-Func
    }
  } finally {
    & deactivate
  }
}

main