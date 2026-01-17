$ErrorActionPreference = 'Stop';

$packageName = 'html-help-workshop'
$url = 'https://web.archive.org/web/20200918004813/https://download.microsoft.com/download/0/A/9/0A939EF6-E31C-430F-A3DF-DFAE7960D564/htmlhelp.exe'
$checksum = '53899be5da83419d772d5b97e653da7c'

# a temporary directory for extracted installer files
$temp_dir = Join-Path $Env:TEMP ([System.Guid]::NewGuid().ToString())
New-Item -Type Directory -Path $temp_dir | Out-Null

# download auto-extracting zip installer
$htmlhelp_exe = Join-Path $temp_dir "htmlhelp.exe"
Get-ChocolateyWebFile $packageName $htmlhelp_exe $url -checksum $checksum

# extract to temporary directory in quiet mode
$htmlhelp_extracted = Join-Path $temp_dir "htmlhelp"
Start-ChocolateyProcessAsAdmin "/Q ""/T:$htmlhelp_extracted"" /C" $htmlhelp_exe

# comment out the line which runs hhupd.exe (the automatic updater) after installation
# the updater will pop up a dialog telling us we are running the latest version already
$htmlhelp_install = Join-Path $htmlhelp_extracted "htmlhelp.inf"
$htmlhelp_install_fixed = Join-Path $htmlhelp_extracted "htmlhelp_fixed.inf"
(Get-Content $htmlhelp_install) -replace '^\"hhupd.exe /C', ';$0' | Set-Content $htmlhelp_install_fixed

# find the 32-bit rundll; always install as 32-bit as there is no 64-bit distribution
$rundll_exe = Join-Path $Env:SystemRoot "System32\rundll32.exe"
$rundll_exe6432 = Join-Path $Env:SystemRoot "SysWOW64\rundll32.exe"
$rundll = @($rundll_exe6432,$rundll_exe) | Where { Test-Path $_ } | Select-Object -First 1

# install from INF
# https://msdn.microsoft.com/en-us/library/gg441316%28v=vs.85%29.aspx
$section = "" # default entrypoint
$flags = 3 # LIS_QUIET | LIS_NOGRPCONV
$reboot = "N"
Start-ChocolateyProcessAsAdmin "advpack.dll,LaunchINFSection ""$htmlhelp_install_fixed"",$section,$flags,$reboot" $rundll

# cleanup temp directory
Remove-Item -Path $temp_dir -Recurse
