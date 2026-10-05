#requires -Version 7.0
. "$PSScriptRoot/windows/common.ps1"
[pscustomobject]@{
    RegisteredFrontend = Get-MachineWeaselRoot
    UserData = Get-ItemPropertyValue -LiteralPath $RegistryPath -Name RimeUserDir -ErrorAction SilentlyContinue
    ModelPid = (Get-OwnedProcess 'model').Id
    WeaselPid = (Get-OwnedProcess 'weasel').Id
} | ConvertTo-Json
