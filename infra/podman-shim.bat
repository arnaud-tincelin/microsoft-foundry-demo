@echo off
(echo SHIM CALLED: %*) >> c:\Github\microsoft-foundry-demo\infra\shim.log

REM Check for version flag variants
if "%1"=="--version" (
    echo Docker version 20.10.24, build 297e128
    exit /b 0
)

if "%1"=="-v" (
    echo Docker version 20.10.24, build 297e128
    exit /b 0
)

if "%1"=="version" (
    (echo RETURNING DOCKER VERSION STRING) >> c:\Github\microsoft-foundry-demo\infra\shim.log
    REM Return Docker-style version output for azd compatibility
    echo Client: Docker Engine - Community
    echo  Version:           20.10.24
    echo  API version:       1.41
    echo  Go version:        go1.19.7
    echo  Git commit:        297e128
    echo  Built:             Tue Apr  4 18:17:06 2023
    echo  OS/Arch:           windows/amd64
    echo  Context:           default
    echo.
    echo Server: Docker Engine - Community
    echo  Engine:
    echo   Version:          20.10.24
    echo   API version:      1.41 (minimum version 1.12)
    echo   Go version:       go1.19.7
    echo   Git commit:       5d6db84
    echo   Built:            Tue Apr  4 18:23:22 2023
    echo   OS/Arch:          linux/amd64
    exit /b 0
)

REM Pass everything else to Podman
(echo PASSING TO PODMAN: %*) >> c:\Github\microsoft-foundry-demo\infra\shim.log
podman %*