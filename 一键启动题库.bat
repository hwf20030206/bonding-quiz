@echo off
chcp 65001 >nul
echo ========================================
echo       正在初始化键合题库学习系统...
echo ========================================
echo.
echo 正在检查并安装必要的依赖环境，请耐心等待（首次运行可能需要1-2分钟）...

:: 静默安装依赖
pip install streamlit pandas openpyxl -q

echo.
echo 环境准备就绪！正在为您唤醒网页...
echo.

:: 自动定位到当前文件夹并启动网页
cd /d "%~dp0"
streamlit run web_quiz.py

pause