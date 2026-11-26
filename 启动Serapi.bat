@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo   Serapi 一键启动
echo ========================================
echo.

if not exist "app\main.py" (
    echo [错误] 未找到 app\main.py。
    echo 请确认批处理放在解压后的 Serapi 目录内。
    goto :fail
)
if not exist "requirements.txt" (
    echo [错误] 未找到 requirements.txt。
    goto :fail
)

if not exist ".venv\Scripts\python.exe" (
    set "BASE_PY="
    where py >nul 2>nul
    if not errorlevel 1 (
        rem 首选默认 py -3（可能是 3.15/3.16），只接受 >=3.14
        py -3 -c "import sys; raise SystemExit(0 if sys.version_info>=(3,14) else 1)" >nul 2>nul
        if not errorlevel 1 set "BASE_PY=py -3"
    )
    if not defined BASE_PY (
        where py >nul 2>nul
        if not errorlevel 1 (
            py -3.14 -c "import sys" >nul 2>nul
            if not errorlevel 1 set "BASE_PY=py -3.14"
        )
    )
    if not defined BASE_PY (
        where python >nul 2>nul
        if not errorlevel 1 (
            python -c "import sys; raise SystemExit(0 if sys.version_info>=(3,14) else 1)" >nul 2>nul
            if not errorlevel 1 set "BASE_PY=python"
        )
    )
    if not defined BASE_PY (
        echo [错误] 未检测到 Python 3.14 或更高版本。
        echo 请先安装 Python 3.14+，并在安装时勾选 Add to PATH。
        goto :fail
    )

    echo 首次运行：正在创建独立 Python 环境……
    %BASE_PY% -m venv ".venv"
    if errorlevel 1 (
        echo [错误] 虚拟环境创建失败。
        goto :fail
    )
)

set "VENV_PY=%CD%\.venv\Scripts\python.exe"
if not exist ".venv\.serapi-ready" (
    echo 首次运行：正在安装依赖，请保持网络连接……
    "%VENV_PY%" -m pip install -r "requirements.txt"
    if errorlevel 1 (
        echo [错误] 依赖安装失败，请检查网络后重新双击本文件。
        goto :fail
    )
    >".venv\.serapi-ready" echo Serapi dependencies installed
)

echo 正在启动 Serapi……
echo.
"%VENV_PY%" -m app.main
if errorlevel 1 (
    echo.
    echo [错误] Serapi 异常退出，请保留本窗口中的报错信息。
    goto :fail
)

exit /b 0

:fail
echo.
pause
exit /b 1
