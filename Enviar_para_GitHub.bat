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

if exist .git (
    echo [INFO] Repositório Git local já existe.
    echo Escolha uma opção:
    echo [1] Apenas enviar atualizações (git add, commit, push) - RECOMENDADO
    echo [2] Reiniciar repositório do zero (limpar histórico local e refazer vínculo)
    echo.
    set /p opcao="Digite a opção (1 ou 2) e pressione ENTER: "
) else (
    set opcao=2
)

if "%opcao%"=="1" (
    echo.
    echo [1/3] Preparando atualizações...
    git add .
    
    echo.
    echo [2/3] Criando commit de atualização...
    set /p msg="Digite a descrição da atualização (ex: Adiciona versao mobile) e pressione ENTER: "
    if "%msg%"=="" set msg="Atualização do GeoPortal - Mobile e Escala"
    git commit -m "%msg%"
    
    echo.
    echo [3/3] Enviando atualizações para o GitHub...
    git push origin main
    
    goto fim
)

if "%opcao%"=="2" (
    if exist .git (
        echo.
        echo [INFO] Limpando registros antigos do Git para evitar erros de arquivos pesados...
        rd /s /q .git
    )
    
    echo [1/4] Inicializando o repositório Git...
    git init

    echo.
    echo [2/4] Adicionando os arquivos do GeoPortal...
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
    
    goto fim
)

:fim
echo.
if %errorlevel% equ 0 (
    echo ===================================================
    echo [SUCESSO] Operação concluída com sucesso!
    echo.
    echo Se você ativou o GitHub Pages nas configurações do 
    echo repositório, seu site já está sendo atualizado online.
    echo ===================================================
) else (
    echo.
    echo [ERRO] Ocorreu um problema ao enviar. 
    echo Verifique sua conexão e se você está logado no Git no seu computador.
)
echo.
pause
