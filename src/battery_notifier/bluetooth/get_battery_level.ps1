$BTDeviceFriendlyName = "WH-1000XM4 Hands-Free AG"
$BTHDevices = Get-PnpDevice -FriendlyName "*$($BTDeviceFriendlyName)*"

if (!$BTHDevices) {
    Write-Host "-1"
    exit
}

foreach ($Device in $BTHDevices) {
    $BatteryProperty = Get-PnpDeviceProperty -InstanceId $Device.InstanceId -KeyName '{104EA319-6EE2-4701-BD47-8DDBF425BBE5} 2' |
    Where-Object { $_.Type -ne 'Empty' } |
    Select-Object -ExpandProperty Data

    if ($BatteryProperty) {
        Write-Host $BatteryProperty
        exit 0
    }
}

Write-Host "-1"
