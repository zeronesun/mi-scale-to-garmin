# 🎉 mi-scale-to-garmin v1.0.0

Automatically sync **body composition measurements** from your Mi/Xiaomi body fat scale (via Mi Fitness) to your **Garmin Connect** account. This is the first stable release.

## ✨ Features

- **Automatic sync**: fetch body fat scale data from Mi Fitness, generate Garmin-compatible FIT files, and upload to Garmin Connect
- **More than weight**: syncs 10 measurement fields (weight, BMI, body fat %, body water %, bone mass, muscle mass, metabolic age, visceral fat rating, basal metabolism, physique rating)
- **Full local backup**: all 28 metrics measured by the Mi scale stored locally (including protein, waist-hip ratio, etc. that FIT doesn't support)
- **Two interfaces**: GUI (PyQt6, multi-user management) + CLI (supports scheduled auto-sync)
- **Multi-user support**: manage multiple Mi + Garmin account pairs in one program
- **Data security**: passwords never stored, tokens encrypted, account desensitization

## 📦 Downloads

| Platform | File |
|----------|------|
| Windows x64 | `mi-scale-to-garmin-windows-x64-v1.0.0.zip` |
| macOS (Apple Silicon) | `mi-scale-to-garmin-macos-arm64-v1.0.0.dmg` |
| macOS (Intel) | `mi-scale-to-garmin-macos-x64-v1.0.0.dmg` |

> Linux is not yet published via CI; run from source (see README).

## 🚀 Quick Start

1. Download the installer for your platform
2. On first run, follow the guided auth (Mi + Garmin, once each)
3. Syncs automatically afterward; configure a scheduled task if desired

Full documentation: [README](https://github.com/zeronesun/mi-scale-to-garmin#readme)

## ⚠️ Notes

- macOS builds are **unsigned** — on first open, right-click → Open → Confirm
- First use requires one-time auth (password entered with hidden echo)
- Garmin server region: China `CN`, international `COM`

---

# 中文说明（简体中文）

将小米体脂秤测量数据自动同步到佳明（Garmin Connect）的首个正式版本。

## ✨ 功能亮点

- **自动同步**：从小米运动健康拉取体脂秤数据，生成 Garmin 兼容的 FIT 文件并上传到佳明 Connect
- **不止体重**：同步 10 项测量字段（体重、BMI、体脂率、体水率、骨量、肌肉量、代谢年龄、内脏脂肪等级、基础代谢、身体评分）
- **本地全量备份**：小米秤测出的全部 28 项指标存本地（含 FIT 不支持的蛋白质、腰臀比等）
- **双形态界面**：图形界面（GUI，多用户管理）+ 命令行（CLI，可定时自动同步）
- **多用户支持**：一个程序管理多个小米 + 佳明账号组合
- **数据安全**：密码不落盘、token 加密存储、账号脱敏标识

## 📦 安装包

| 平台 | 文件 |
|------|------|
| Windows x64 | `mi-scale-to-garmin-windows-x64-v1.0.0.zip` |
| macOS (Apple Silicon) | `mi-scale-to-garmin-macos-arm64-v1.0.0.dmg` |
| macOS (Intel) | `mi-scale-to-garmin-macos-x64-v1.0.0.dmg` |

> Linux 版暂未随 CI 发布，可用源码方式运行（见 README）。

## 🚀 快速开始

1. 下载对应平台的安装包
2. 首次运行按引导完成认证（小米 + 佳明各一次）
3. 之后自动同步，可配置定时任务

详细说明见 [README](https://github.com/zeronesun/mi-scale-to-garmin#readme)。

## ⚠️ 注意事项

- macOS 安装包**未签名**，首次打开需右键 → 打开 → 确认
- 首次使用需完成一次认证（密码隐藏回显）
- 佳明服务器区域：中国区选 `CN`，国际区选 `COM`
