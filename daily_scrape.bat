@echo off
REM Daily Wellfound Scraper - Scheduled Task Runner
REM This batch file runs the daily scraper for both ML Engineer and Data Scientist roles.
REM
REM To import into Task Scheduler:
REM   1. Open Task Scheduler (taskschd.msc)
REM   2. Click "Import Task..."
REM   3. Select the wellfound_daily_scrape.xml file
REM
REM Or run manually:
REM   daily_scrape.bat

cd /d "D:\Wellfound_Scrape"
python daily_scrape.py --pages 3 --delay 3.0
