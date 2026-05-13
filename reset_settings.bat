@echo off
echo Fetching latest changes from origin...
git fetch origin
if %errorlevel% neq 0 goto error

echo Performing hard reset to origin/main...
git reset --hard origin/main
if %errorlevel% neq 0 goto error

echo Success! Local branch is synchronized with origin/main.
pause
exit

:error
echo An error occurred during execution.
pause
exit /b 1