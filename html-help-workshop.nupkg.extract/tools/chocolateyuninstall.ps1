$ErrorActionPreference = 'Stop';

$packageName = 'html-help-workshop'

# find the uninstaller
$machine_key = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\hhw.exe'
$machine_key6432 = 'HKLM:\SOFTWARE\Wow6432Node\Microsoft\Windows\CurrentVersion\App Paths\hhw.exe'
$htmlhelp_dir = Get-ItemProperty -Path @($machine_key6432,$machine_key) -ErrorAction SilentlyContinue |
  Select-Object -ExpandProperty Path -First 1

if (-not $htmlhelp_dir) {
  Write-Warning "$packageName has already been uninstalled by other means."
  return
}

$htmlhelp_uninstall = Join-Path $htmlhelp_dir "htmlhelp.inf"

# find the 32-bit rundll
$rundll_exe = Join-Path $Env:SystemRoot "System32\rundll32.exe"
$rundll_exe6432 = Join-Path $Env:SystemRoot "SysWOW64\rundll32.exe"
$rundll = @($rundll_exe6432,$rundll_exe) | Where { Test-Path $_ } | Select-Object -First 1

# uninstall from INF
# https://msdn.microsoft.com/en-us/library/gg441316%28v=vs.85%29.aspx
$section = "" # default entrypoint
$flags = 3 # LIS_QUIET | LIS_NOGRPCONV
$reboot = "N"
Start-ChocolateyProcessAsAdmin "advpack.dll,LaunchINFSection ""$htmlhelp_uninstall"",$section,$flags,$reboot" $rundll
