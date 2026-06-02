@echo off
chcp 65001 > nul
title Assistente de Envio ao GitHub - GeoPortal Ubaíra
echo ===================================================
echo   GeoPortal Ubaíra - Assistente de Envio ao GitHub
echo ===================================================
echo.

:: Verificar se o Git está instalado
where git >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERRO] O Git não foi encontrado no seu computador.
    echo.
    echo Para continuar, você precisa instalar o Git:
    echo 1. Baixe em: https://git-scm.com/download/win
    echo 2. Instale com as configurações padrão.
    echo 3. Após a instalação, feche esta janela e execute este arquivo novamente.
    echo.
    pause
    exit
)

echo [OK] Git encontrado!
echo.

:: Verificar se já existe a pasta .git
if exist .git (
    echo [INFO] Limpando registros antigos do Git para evitar erros de arquivos pesados...
    rd /s /q .git
)

echo [1/4] Inicializando o repositório Git...
git init

echo.
echo [2/4] Adicionando os arquivos do GeoPortal...
:: O .gitignore criado garantirá que as pastas de dados brutos pesados sejam ignoradas
git add .

echo.
echo [3/4] Salvando alterações localmente (Commit)...
git commit -m "Upload do GeoPortal Ubaíra"

echo.
echo ---------------------------------------------------
echo Crie um repositório no seu GitHub:
echo 1. Acesse: https://github.com/new
echo 2. Nome do repositório: geoportal-ubaira
echo 3. Deixe como PUBLIC (público)
echo 4. NÃO marque "Add a README", ".gitignore" ou "license".
echo 5. Clique em "Create repository".
echo ---------------------------------------------------
echo.

set /p repo_url="Cole aqui o link HTTPS do seu repositório (ex: https://github.com/usuario/geoportal-ubaira.git) e pressione ENTER: "

if "%repo_url%"=="" (
    echo [ERRO] URL inválida! Operação cancelada.
    pause
    exit
)

echo.
echo [4/4] Enviando os arquivos para o GitHub...
git branch -M main
git remote add origin %repo_url%
git push -u origin main

echo.
if %errorlevel% equ 0 (
    echo ===================================================
    echo [SUCESSO] Seu GeoPortal foi enviado com sucesso!
    echo.
    echo Agora, para ativar o site:
    echo 1. Entre nas configurações (Settings) do repositório no GitHub.
    echo 2. Clique em "Pages" no menu esquerdo.
    echo 3. Em "Branch", mude de "None" para "main" e clique em Save.
    echo 4. Aguarde 1 minuto e seu site estará no ar!
    echo ===================================================
) else (
    echo.
    echo [ERRO] Ocorreu um problema ao enviar. 
    echo Verifique sua conexão e se você está logado no Git no seu computador.
)
echo.
pause
