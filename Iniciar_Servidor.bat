@echo off
chcp 65001 > nul
title Servidor GeoPortal Ubaíra - Localhost
echo ===================================================
echo   GeoPortal Ubaíra - Iniciando Servidor Local
echo ===================================================
echo.

:: Procurar pelo ambiente QGIS
set "QGIS_PATH=C:\Program Files\QGIS 3.40.8"
if not exist "%QGIS_PATH%\bin\o4w_env.bat" (
    echo [AVISO] QGIS 3.40.8 não encontrado no caminho padrão. Procurando outras versões...
    for /d %%d in ("C:\Program Files\QGIS 3.*") do (
        if exist "%%d\bin\o4w_env.bat" (
            set "QGIS_PATH=%%d"
            goto :encontrado
        )
    )
    echo [ERRO] Não foi possível encontrar uma instalação do QGIS.
    echo O Python do QGIS é necessário para as bibliotecas espaciais (GDAL, OGR).
    echo Verifique se o QGIS está instalado em "C:\Program Files".
    pause
    exit /b
)

:encontrado
echo [OK] QGIS encontrado em: "%QGIS_PATH%"
echo [INFO] Inicializando variáveis de ambiente do QGIS...
echo.

:: Abrir o navegador automaticamente
echo [INFO] Abrindo o portal no navegador: http://localhost:8080 ...
start http://localhost:8080

:: Rodar o servidor Python
cmd.exe /c "call "%QGIS_PATH%\bin\o4w_env.bat" && python -u server.py"

pause
