@echo off
chcp 65001 >nul
title 长益剪辑Agent v5.1

echo ╔══════════════════════════════════════╗
echo ║    🎬 长益剪辑Agent v5.1            ║
echo ╚══════════════════════════════════════╝
echo.

:: 环境检测
python setup.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ⚠️ 环境不完整·请先修复上述 ❌ 项
    pause
    exit /b 1
)

echo.
echo ┌──────────────────────────────────────┐
echo │  选择模式:                            │
echo │  1. 素材出片（有视频素材）              │
echo │  2. 剪映草稿（四类素材·推荐）           │
echo │  3. 数字人（照片+脚本）                │
echo │  4. 带货视频（产品图+价格）            │
echo │  5. 批量处理（CSV文件）                │
echo │  6. 系统诊断                           │
echo └──────────────────────────────────────┘
set /p mode="请输入数字(1-6): "

if "%mode%"=="1" goto clip_mode
if "%mode%"=="2" goto jianying_mode
if "%mode%"=="3" goto digital_human
if "%mode%"=="4" goto product_mode
if "%mode%"=="5" goto batch_mode
if "%mode%"=="6" goto diagnose
echo 无效选择
pause
exit /b 1

:clip_mode
set /p script="输入脚本: "
set /p video="输入视频路径: "
python demo.py "%script%" --video "%video%"
goto end

:jianying_mode
set /p script="输入脚本: "
set /p talking="口播出镜视频: "
set /p env="店铺环境素材(逗号分隔): "
set /p product="产品展示素材(逗号分隔): "
python demo.py --jianying --script "%script%" --talking "%talking%" --env "%env%" --product "%product%"
goto end

:digital_human
set /p script="输入脚本: "
set /p photo="输入照片路径: "
python demo.py "%script%" --photo "%photo%"
goto end

:product_mode
set /p script="输入价格+卖点(逗号分隔): "
set /p img="输入产品图片: "
python demo.py "%script%" --product-img "%img%"
goto end

:batch_mode
set /p csv="输入CSV文件路径: "
python batch.py "%csv%"
goto end

:diagnose
python -c "from clip_agent.health import print_health_report; print_health_report()"
goto end

:end
echo.
echo ✅ 完成！
pause
