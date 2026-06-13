@echo off
chcp 65001 > nul
title Servidor GeoPortal Ubaíra - Localhost
echo ===================================================
echo   GeoPortal Ubaíra - Iniciando Servidor Local
echo ===================================================
echo.

:: Procurar pelo ambiente QGIS padrao
set "QGIS_PATH=C:\Program Files\QGIS 3.40.8"
if exist "%QGIS_PATH%\bin\o4w_env.bat" goto :encontrado

:: Se nao existir, tentar buscar outra versao 3.x
echo [AVISO] QGIS 3.40.8 nao encontrado no caminho padrao. Procurando outras versoes...

:: Fazer a busca de forma plana
for /d %%d in ("C:\Program Files\QGIS 3.*") do if exist "%%d\bin\o4w_env.bat" set "QGIS_PATH=%%d"
if exist "%QGIS_PATH%\bin\o4w_env.bat" goto :encontrado

echo [ERRO] Nao foi possivel encontrar uma instalacao do QGIS.
echo O Python do QGIS e necessario para as bibliotecas espaciais (GDAL, OGR).
echo Verifique se o QGIS esta instalado em "C:\Program Files".
pause
exit /b

:encontrado
echo [OK] QGIS encontrado em: "%QGIS_PATH%"
echo [INFO] Inicializando variaveis de ambiente do QGIS...
echo.

:: Abrir o navegador automaticamente
echo [INFO] Abrindo o portal no navegador: http://localhost:8080 ...
start http://localhost:8080

:: Inicializar o ambiente e rodar o servidor Python na mesma janela
call "%QGIS_PATH%\bin\o4w_env.bat"
python -u server.py

pause
