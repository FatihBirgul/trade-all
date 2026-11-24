@echo off
setlocal EnableExtensions DisableDelayedExpansion
title TRADE AI V3 - MT5, Tailscale ve 4 Sunucu Baslatici

set "WEB=%~dp0..\trade-ai-forex-web"
set "UI=%~dp0..\trade-ai-forex-web-v3-integration"
set "CORE=%~dp0..\day-trader-skill"
set "V2FILE=%~dp0..\trade-ai-v2-antigravity\backend\market_ai\engines\candlestick.py"
rem MT5 farkli bir dizindeyse buraya tam terminal64.exe yolunu yazabilirsiniz.
rem Bos birakildiginda Exness / MetaTrader 5 otomatik aranir.
rem MT5_EXE ortam degiskeni terminal yolunu belirleyebilir.

if not exist "%UI%\package.json" (
    echo HATA: PWA klasoru bulunamadi: "%UI%"
    pause
    exit /b 1
)
if not exist "%CORE%\forex\api.py" (
    echo HATA: V3 Core bulunamadi: "%CORE%"
    pause
    exit /b 1
)
if not exist "%V2FILE%" (
    echo HATA: V2 candlestick dosyasi bulunamadi: "%V2FILE%"
    pause
    exit /b 1
)

echo TRADE AI V3 baslatiliyor (Tailscale + MT5 + 4 sunucu)...
echo.

rem Tailscale servisini ve tepsi simgesini baslat; bagli degilse baglanmayi dene.
call :TailscaleBaslat
echo.

rem MT5'i ilk once baslat; daha once aciksa tekrar acma.
call :MT5Baslat
if errorlevel 1 (
    echo [UYARI] MT5 otomatik bulunamadi. Sunucular yine de acilacak.
    echo [UYARI] Dosyanin basindaki MT5_EXE alanina terminal64.exe yolunu yazabilirsiniz.
)
echo.

call :PortKullanimda 8005
if not errorlevel 1 goto Skip8005
echo [8005] MT5 Bridge aciliyor...
start "TRADE AI - MT5 Bridge 8005" /MAX powershell.exe -NoLogo -NoExit -NoProfile -Command "Set-Location -LiteralPath $env:WEB; $Host.UI.RawUI.WindowTitle='TRADE AI - MT5 Bridge [8005]'; py -3.11 -B -m uvicorn mt5_bridge:app --host 127.0.0.1 --port 8005"
goto Done8005
:Skip8005
echo [8005] Port zaten kullanimda; ikinci sunucu acilmadi.
:Done8005

call :PortKullanimda 8008
if not errorlevel 1 goto Skip8008
echo [8008] V3 Analiz API aciliyor...
start "TRADE AI - Analiz API 8008" /MAX powershell.exe -NoLogo -NoExit -NoProfile -Command "Set-Location -LiteralPath $env:CORE; $Host.UI.RawUI.WindowTitle='TRADE AI - Analiz API [8008]'; $env:MT5_ANALYSIS_POLICY='REAL_READONLY_DATA'; $env:MT5_EXPECTED_REAL_SERVER='Exness-MT5Real50'; $env:MT5_EXPECTED_REAL_CURRENCY='USC'; if(-not $env:MT5_SYMBOL_MAP){$env:MT5_SYMBOL_MAP=(@{XAUUSD='XAUUSDc'; EURUSD='EURUSDc'; GBPUSD='GBPUSDc'; USDJPY='USDJPYc'; CHFJPY='CHFJPYc'; EURCAD='EURCADc'; USDCAD='USDCADc'; USDCHF='USDCHFc'; EURGBP='EURGBPc'; EURCHF='EURCHFc'; GBPCHF='GBPCHFc'; NZDUSD='NZDUSDc'; EURAUD='EURAUDc'; CADJPY='CADJPYc'; NZDJPY='NZDJPYc'; AUDUSD='AUDUSDc'; EURJPY='EURJPYc'; GBPJPY='GBPJPYc'; AUDJPY='AUDJPYc'} | ConvertTo-Json -Compress)}; $env:MT5_BROKER_HOURS='{}'; $env:V2_CHART_GIT_ROOT=(Resolve-Path (Join-Path $env:CORE '../trade-ai-v2-antigravity')).Path; $env:V2_CANDLESTICK_FILE=$env:V2FILE; $env:V2_CANDLESTICK_SHA256='45ee833fd3a5ffd178a4ee565e5914f79e9fb0b1c2aa62fe16b703057f63542c'; $env:PYTHONDONTWRITEBYTECODE='1'; py -3.11 -B -m uvicorn forex.api:app --host 127.0.0.1 --port 8008"
goto Done8008
:Skip8008
echo [8008] Port zaten kullanimda; ikinci sunucu acilmadi.
:Done8008

call :PortKullanimda 8007
if not errorlevel 1 goto Skip8007
echo [8007] Haber Bridge aciliyor...
start "TRADE AI - Haber Bridge 8007" /MAX powershell.exe -NoLogo -NoExit -NoProfile -Command "Set-Location -LiteralPath $env:WEB; $Host.UI.RawUI.WindowTitle='TRADE AI - Haber Bridge [8007]'; py -3.11 -B -m uvicorn news_bridge:app --host 127.0.0.1 --port 8007"
goto Done8007
:Skip8007
echo [8007] Port zaten kullanimda; ikinci sunucu acilmadi.
:Done8007

call :PortKullanimda 5173
if not errorlevel 1 goto Skip5173
echo [5173] PWA aciliyor...
start "TRADE AI - PWA 5173" /MAX powershell.exe -NoLogo -NoExit -NoProfile -Command "Set-Location -LiteralPath $env:UI; $Host.UI.RawUI.WindowTitle='TRADE AI - PWA [5173]'; npm.cmd run dev -- --host 127.0.0.1 --port 5173 --strictPort"
goto Done5173
:Skip5173
echo [5173] Port zaten kullanimda; ikinci sunucu acilmadi.
:Done5173

echo.
echo Web uygulamasi hazir olunca varsayilan tarayicida acilacak.
rem 5173 hazir olana kadar en fazla 60 saniye bekle; acilmadiysa tarayici acma.
start "TRADE AI - Web Acici" /MIN powershell.exe -NoLogo -NoProfile -WindowStyle Hidden -Command "$url='http://127.0.0.1:5173/'; for($i=0; $i -lt 60; $i++){ try { $r=Invoke-WebRequest -UseBasicParsing -Uri $url -TimeoutSec 2; if($r.StatusCode -eq 200){ Start-Process $url; exit 0 } } catch {} ; Start-Sleep -Seconds 1 }"
echo Kontrol tamamlandi. Acilan PowerShell pencerelerini kapatmayin.
echo PWA adresi: http://127.0.0.1:5173/
exit /b 0

:TailscaleBaslat
rem Kurulu Tailscale yazilimini kullanir. Yeniden kurmaz, diger portlari degistirmez.
rem Mevcut baglanti varsa aynen birakir; baglanti kapaliysa "tailscale up" dener.
powershell.exe -NoLogo -NoProfile -Command "$ErrorActionPreference='SilentlyContinue'; $dirs=@(); foreach($root in @($env:ProgramFiles,${env:ProgramFiles(x86)},$env:LOCALAPPDATA)){if($root){foreach($folder in @('Tailscale','Tailscale IPN')){$dirs+= (Join-Path $root $folder)}}}; $gui=$null; $cli=$null; foreach($d in $dirs){if(-not $gui){$p=Join-Path $d 'tailscale-ipn.exe'; if(Test-Path -LiteralPath $p -PathType Leaf){$gui=$p}}; if(-not $cli){$p=Join-Path $d 'tailscale.exe'; if(Test-Path -LiteralPath $p -PathType Leaf){$cli=$p}}}; if(-not $cli){$cmd=Get-Command 'tailscale.exe' -ErrorAction SilentlyContinue; if($cmd){$cli=$cmd.Source}}; $svc=Get-Service -Name 'Tailscale' -ErrorAction SilentlyContinue; if($svc -and $svc.Status -ne 'Running'){try{Start-Service -Name 'Tailscale' -ErrorAction Stop; Write-Host '[TAILSCALE] Windows servisi baslatildi.'}catch{Write-Host '[TAILSCALE] UYARI: Servis acilamadi; yonetici izni gerekebilir.'}}; $already=Get-Process -Name 'tailscale-ipn' -ErrorAction SilentlyContinue; if($already){Write-Host '[TAILSCALE] Uygulama zaten acik.'}elseif($gui){try{Start-Process -FilePath $gui -ErrorAction Stop; Write-Host '[TAILSCALE] Uygulama acildi.'}catch{Write-Host '[TAILSCALE] UYARI: Arayuz baslatilamadi.'}}else{Write-Host '[TAILSCALE] UYARI: Arayuz (tailscale-ipn.exe) bulunamadi.'}; if($cli){$state=$null; try{$o= & $cli status --json 2>$null | Out-String; if($o){$state=($o | ConvertFrom-Json).BackendState}}catch{}; if($state -eq 'Running'){Write-Host '[TAILSCALE] Baglanti aktif.'}else{try{Start-Process -FilePath $cli -ArgumentList 'up' -WindowStyle Hidden -ErrorAction Stop; Write-Host '[TAILSCALE] Baglanti baslatma istegi gonderildi. Gerekiyorsa uygulamadan oturum acin.'}catch{Write-Host '[TAILSCALE] UYARI: Baglanma istegi baslatilamadi. Uygulamadan Connect secin.'}}}else{Write-Host '[TAILSCALE] UYARI: tailscale.exe bulunamadi. Diger sunucular acilmaya devam ediyor.'}"
exit /b 0

:MT5Baslat
rem MetaTrader 5 zaten aciksa ikinci kopyayi baslatma.
rem Oncelik: elle tanimlanan yol, Exness dizinleri, MetaTrader 5 dizinleri,
rem Windows kurulu program kayitlari ve Baslat menusu / masaustu kisayollari.
powershell.exe -NoLogo -NoProfile -Command "$ErrorActionPreference='SilentlyContinue'; if(Get-Process -Name terminal64 -ErrorAction SilentlyContinue){Write-Host '[MT5] Zaten acik; ikinci kez baslatilmadi.'; exit 0}; $c=@(); if($env:MT5_EXE){$c+= $env:MT5_EXE}; $bases=@($env:ProgramFiles,${env:ProgramFiles(x86)},$env:LOCALAPPDATA); $names=@('Exness MetaTrader 5','MetaTrader 5 EXNESS','MetaTrader 5','Exness\MetaTrader 5','Programs\MetaTrader 5'); foreach($b in $bases){if($b){foreach($n in $names){$c+= (Join-Path (Join-Path $b $n) 'terminal64.exe')}; $dirs=Get-ChildItem -LiteralPath $b -Directory | Where-Object {$_.Name -match 'Exness|MetaTrader|MetaQuotes'}; foreach($d in $dirs){$c+= (Join-Path $d.FullName 'terminal64.exe')}}}; $regs=Get-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*','HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*','HKLM:\Software\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*' | Where-Object {$_.DisplayName -match 'Exness|MetaTrader'}; foreach($r in $regs){if($r.InstallLocation){$c+= (Join-Path $r.InstallLocation 'terminal64.exe')}; if($r.DisplayIcon){$c+= ($r.DisplayIcon.Trim([char]34) -replace ',\d+$','')}}; $ss=@([Environment]::GetFolderPath('CommonStartMenu'),[Environment]::GetFolderPath('StartMenu'),[Environment]::GetFolderPath('Desktop'),[Environment]::GetFolderPath('CommonDesktopDirectory')); $shell=New-Object -ComObject WScript.Shell; foreach($d in $ss){if($d){$links=Get-ChildItem -LiteralPath $d -Filter '*.lnk' -Recurse | Where-Object {$_.Name -match 'Exness|MetaTrader'}; foreach($l in $links){try{$t=$shell.CreateShortcut($l.FullName).TargetPath; if($t -match 'terminal64\.exe$'){$c+= $t}}catch{}}}}; $p=if($env:MT5_EXE -and (Test-Path -LiteralPath $env:MT5_EXE -PathType Leaf)){$env:MT5_EXE}else{$c | Where-Object {$_ -and (Test-Path -LiteralPath $_ -PathType Leaf)} | Sort-Object @{Expression={if($_ -match 'Exness'){0}else{1}}} | Select-Object -First 1}; if($p){try{Start-Process -FilePath $p -ErrorAction Stop; Write-Host ('[MT5] Acildi: '+$p); exit 0}catch{Write-Host ('[MT5] Acilamadi: '+$_.Exception.Message); exit 1}}; Write-Host '[MT5] terminal64.exe bulunamadi.'; exit 1"
exit /b %errorlevel%

:PortKullanimda
powershell.exe -NoLogo -NoProfile -Command "if (Get-NetTCPConnection -LocalPort %~1 -State Listen -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }" >nul 2>&1
exit /b %errorlevel%
