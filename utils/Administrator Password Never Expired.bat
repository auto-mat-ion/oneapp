@echo off
wmic useraccount where "name='Administrator'" set PasswordExpires=false
exit