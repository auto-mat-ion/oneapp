@echo off
cd /d "C:\Users\Administrator\Desktop\oneapp"
:: Force the reboot, bypass all active sessions, and provide a server reason code
shutdown /r /f /t 2 /d p:4:1 /c "Python Script Triggered Reboot"
