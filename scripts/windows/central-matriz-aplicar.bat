@echo off
rem Central de Chamados na matriz (decisao 48): o modem da operadora entrega o DNS IPv6 dela aos PCs e nao faz
rem NAT loopback, entao de dentro da matriz o endereco publico nao abre. Enquanto a operadora nao desliga o IPv6
rem da LAN, o arquivo aplicar grava o IP interno do servidor no hosts do Windows; se o hosts estiver protegido
rem (antivirus), grava uma regra de DNS do Windows (NRPT) que manda perguntar esse nome ao servidor.
rem O arquivo desfazer remove as duas. Executar como administrador.
net session >nul 2>&1 || (echo Clique com o botao direito no arquivo e escolha "Executar como administrador". & pause & exit /b 1)
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; $n='chamados.example.com'; $h=Join-Path $env:WINDIR 'System32\drivers\etc\hosts'; try { attrib -r $h; $l=@(Get-Content $h | Where-Object {$_ -notmatch [regex]::Escape($n)}); $l += '192.168.1.10 ' + $n; Set-Content $h $l -Encoding ASCII; 'Regra gravada no arquivo hosts.' } catch { Get-DnsClientNrptRule | Where-Object {$_.Namespace -contains $n} | Remove-DnsClientNrptRule -Force; Add-DnsClientNrptRule -Namespace $n -NameServers 192.168.1.10; 'O arquivo hosts esta protegido; regra gravada no DNS do Windows.' }" || (echo Nao foi possivel gravar a regra. Tire uma foto desta tela e mande ao TI. & pause & exit /b 1)
ipconfig /flushdns >nul
echo.
echo Pronto. Feche o Chrome por completo e abra https://chamados.example.com
pause
