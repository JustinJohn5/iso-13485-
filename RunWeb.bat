@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
title ISO 13485 文件预筛平台 - 网页控制

rem ============================================================
rem  网页服务控制：启动 / 关闭 后端与前端
rem  端口从 backend\.env 与 frontend\.env.development 读取，不在脚本内写死。
rem  用法：
rem    双击运行               进入交互菜单
rem    RunWeb.bat start       启动后端 + 前端
rem    RunWeb.bat stop        关闭后端 + 前端
rem    RunWeb.bat restart     重启
rem    RunWeb.bat status      查看运行状态
rem  MySQL 数据库不归本脚本管理，start/stop 都不会动它。
rem ============================================================

for %%I in ("%~dp0.") do set "ROOT=%%~fI"
set "PY=%ROOT%\backend\.venv\Scripts\python.exe"

call :LoadPorts
if errorlevel 1 goto :End

set "ACTION=%~1"
if "%ACTION%"=="" goto :Menu
if /i "%ACTION%"=="start" goto :Start
if /i "%ACTION%"=="stop" goto :Stop
if /i "%ACTION%"=="restart" goto :Restart
if /i "%ACTION%"=="status" goto :Status
goto :Usage

rem ---------- 交互菜单 ----------
:Menu
set "MENU_MODE=1"
echo.
echo ============================================================
echo   ISO 13485 文件预筛平台   后端 %BACKEND_PORT% / 前端 %FRONTEND_PORT%
echo ============================================================
call :ShowState
echo.
echo   1. 启动网页
echo   2. 关闭网页
echo   3. 重启网页
echo   4. 查看状态
echo   0. 退出
echo.
set "SEL="
set /p "SEL=请选择 [1/2/3/4/0]："
if "%SEL%"=="1" goto :Start
if "%SEL%"=="2" goto :Stop
if "%SEL%"=="3" goto :Restart
if "%SEL%"=="4" goto :Status
goto :End

rem ---------- 动作入口 ----------
:Start
echo.
echo [启动] 正在启动网页服务……
call :DoStart
goto :Pause

:Stop
echo.
echo [关闭] 正在停止网页服务……
call :DoStop
goto :Pause

:Restart
echo.
echo [重启] 先关闭再启动……
call :DoStop
call :DoStart
goto :Pause

:Status
echo.
call :ShowState
goto :Pause

rem ---------- 具体实现 ----------
:DoStart
call :PortUp %BACKEND_PORT%
if not errorlevel 1 (
    echo   [跳过] 后端 %BACKEND_PORT% 已在运行
) else (
    if not exist "%PY%" (
        echo   [错误] 未找到后端虚拟环境解释器：
        echo          %PY%
        echo          请先按 deploy.md 完成 backend 的虚拟环境与依赖安装。
        exit /b 1
    )
    pushd "%ROOT%\backend"
    start "ISO13485 后端 %BACKEND_PORT%" /min cmd /c "set PYTHONIOENCODING=utf-8 && .venv\Scripts\python.exe Run.py 1>.RunWeb.log 2>&1"
    popd
    echo   [启动] 后端进程已拉起，等待端口 %BACKEND_PORT% 就绪……
    call :WaitPort %BACKEND_PORT% 40
    if errorlevel 1 (
        echo   [警告] 后端启动超时，日志见 %ROOT%\backend\.RunWeb.log
        call :ShowLogTail "%ROOT%\backend\.RunWeb.log"
    ) else (
        echo   [就绪] 后端已监听 %BACKEND_PORT%
    )
)

call :PortUp %FRONTEND_PORT%
if not errorlevel 1 (
    echo   [跳过] 前端 %FRONTEND_PORT% 已在运行
) else (
    if not exist "%ROOT%\frontend\node_modules" (
        echo   [错误] 未找到前端依赖目录 frontend\node_modules
        echo          请先在 frontend 目录执行：npm ci
        exit /b 1
    )
    pushd "%ROOT%\frontend"
    start "ISO13485 前端 %FRONTEND_PORT%" /min cmd /c "chcp 65001>nul && npm run dev 1>.RunWeb.log 2>&1"
    popd
    echo   [启动] 前端进程已拉起，等待端口 %FRONTEND_PORT% 就绪……
    call :WaitPort %FRONTEND_PORT% 60
    if errorlevel 1 (
        echo   [警告] 前端启动超时，日志见 %ROOT%\frontend\.RunWeb.log
        call :ShowLogTail "%ROOT%\frontend\.RunWeb.log"
    ) else (
        echo   [就绪] 前端已监听 %FRONTEND_PORT%
    )
)
echo.
call :ShowState
exit /b 0

:DoStop
call :StopPort %FRONTEND_PORT%
if errorlevel 1 (
    echo   [警告] 前端 %FRONTEND_PORT% 仍被占用
) else (
    echo   [已停] 前端 %FRONTEND_PORT%
)
call :StopPort %BACKEND_PORT%
if errorlevel 1 (
    echo   [警告] 后端 %BACKEND_PORT% 仍被占用
) else (
    echo   [已停] 后端 %BACKEND_PORT%
)
echo   [说明] MySQL 数据库不在本脚本管理范围，未做停止。
exit /b 0

:ShowState
call :PortUp %BACKEND_PORT%
if errorlevel 1 (set "BSTATE=未运行") else (set "BSTATE=运行中")
call :PortUp %FRONTEND_PORT%
if errorlevel 1 (set "FSTATE=未运行") else (set "FSTATE=运行中")
echo   后端 %BACKEND_PORT%：!BSTATE!
echo   前端 %FRONTEND_PORT%：!FSTATE!
if "!FSTATE!"=="运行中" echo   访问地址：http://127.0.0.1:%FRONTEND_PORT%
exit /b 0

rem 打印日志尾部：%1 日志文件路径
:ShowLogTail
set "_log=%~1"
if not exist "!_log!" exit /b 0
echo   ---- 最近日志（!_log!）----
powershell -NoProfile -Command "$ErrorActionPreference='SilentlyContinue'; [Console]::OutputEncoding=[Text.UTF8Encoding]::new($false); Get-Content -LiteralPath '!_log!' -Tail 12 | ForEach-Object { '    ' + $_ }"
echo   --------------------------------
exit /b 0

rem 返回 0 表示端口正在监听，1 表示未监听
:PortUp
netstat -ano -p tcp | findstr /c:"LISTENING" | findstr /c:":%~1 " >nul 2>&1
if errorlevel 1 exit /b 1
exit /b 0

rem 等待端口就绪：%1 端口，%2 最长秒数
:WaitPort
set "_wp=%~1"
set /a _wn=0
:WaitPortLoop
call :PortUp !_wp!
if not errorlevel 1 exit /b 0
set /a _wn+=1
if !_wn! GEQ %~2 exit /b 1
ping -n 2 127.0.0.1 >nul
goto :WaitPortLoop

rem 结束占用端口的进程树：返回 0 表示端口已释放，1 表示仍被占用
:StopPort
set "_sp=%~1"
set /a _killed=0
for /f "tokens=5" %%P in ('netstat -ano -p tcp ^| findstr /c:"LISTENING" ^| findstr /c:":!_sp! "') do (
    if not "%%P"=="0" (
        taskkill /F /T /PID %%P >nul 2>&1
        if errorlevel 1 (
            echo   [提示] PID %%P 已不可见，尝试清理残留的子进程……
            taskkill /F /IM esbuild.exe >nul 2>&1
        )
        set /a _killed+=1
    )
)
if !_killed!==0 (
    echo   [跳过] 端口 %_sp% 当前未在监听
    exit /b 0
)
for /l %%I in (1,1,8) do (
    call :PortUp !_sp!
    if errorlevel 1 exit /b 0
    ping -n 2 127.0.0.1 >nul
)
exit /b 1

rem 读取端口配置
:LoadPorts
set "BACKEND_PORT="
set "FRONTEND_PORT="
if not exist "%ROOT%\backend\.env" (
    echo [错误] 未找到 backend\.env，请先按 deploy.md 创建后端配置文件。
    exit /b 1
)
if not exist "%ROOT%\frontend\.env.development" (
    echo [错误] 未找到 frontend\.env.development，请先按 deploy.md 创建前端配置文件。
    exit /b 1
)
for /f "usebackq tokens=1,* delims==" %%A in ("%ROOT%\backend\.env") do (
    if /i "%%A"=="BACKEND_PORT" set "BACKEND_PORT=%%B"
)
for /f "usebackq tokens=1,* delims==" %%A in ("%ROOT%\frontend\.env.development") do (
    if /i "%%A"=="FRONTEND_PORT" set "FRONTEND_PORT=%%B"
)
call :TrimValue BACKEND_PORT
call :TrimValue FRONTEND_PORT
if not defined BACKEND_PORT (
    echo [错误] backend\.env 中没有 BACKEND_PORT。
    exit /b 1
)
if not defined FRONTEND_PORT (
    echo [错误] frontend\.env.development 中没有 FRONTEND_PORT。
    exit /b 1
)
exit /b 0

:TrimValue
if not defined %~1 exit /b 0
set "_tv=!%~1!"
set "_tv=!_tv: =!"
set "%~1=!_tv!"
exit /b 0

:Pause
if not defined MENU_MODE goto :End
echo.
pause
goto :Menu

:Usage
echo 用法：RunWeb.bat [start ^| stop ^| restart ^| status]
echo   不带参数运行会进入交互菜单。
goto :End

:End
endlocal
exit /b 0
