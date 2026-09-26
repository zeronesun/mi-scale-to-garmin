# 小米体脂秤测量数据自动同步到佳明 (Garmin)

从小米运动健康 (Mi Fitness) 拉取**体脂秤测量数据**（不止体重：含 BMI、体脂率、肌肉量、骨量、内脏脂肪、基础代谢、身体年龄等），生成 Garmin 兼容的 FIT 文件并同步到佳明 Connect 账户。支持所有已导入小米运动健康的体脂秤数据。

**数据去向**：

- **推送到佳明**：FIT `weight_scale` 消息支持的 14 项（体重、BMI、体脂率、体水率、骨量、肌肉量、内脏脂肪等级、基础代谢、身体年龄、身体评分等）
- **仅存本地**（`data/body_data_*.json`）：小米秤测出的全部 28 项（含蛋白质、腰臀比、体型分类等 FIT 格式不支持的指标）

---

## 📖 目录

1. [环境准备](#1-环境准备)
2. [下载与安装](#2-下载与安装)
3. [Docker 部署](#25-docker-部署)
4. [配置](#3-配置)
5. [使用](#4-使用)
6. [进阶](#5-进阶)
7. [数据过滤](#6-数据过滤)
8. [常见问题 (FAQ)](#7-常见问题-faq)

---

## 1. 环境准备

### 项目结构

```text
mi-scale-to-garmin/
├── src/                # 源代码
│   ├── xiaomi/         # 小米登录与数据获取模块
│   ├── garmin/         # 佳明上传与 FIT 文件生成模块（含自研 OAuth 兜底）
│   ├── core/           # 核心：账号哈希/会话存储/引导式初始化/同步编排
│   ├── gui/            # 图形界面（PyQt6，可选）
│   ├── utils/          # 工具：路径/权限加固
│   └── main.py         # 一键同步主程序（CLI 入口）
├── config/             # 配置目录（users.json 放这里或项目根目录均可）
│   └── users.json.example  # 配置模板（含注释，复制为 users.json 使用）
├── docs/               # 详细文档（USAGE / DOCKER_SETUP / FILTER_CONFIG）
├── data/               # 运行产物（自动创建，已 gitignore）
│   ├── xiaomi_auth_*.json  # 小米认证凭证（首次认证后自动生成）
│   ├── .garth/             # 佳明 OAuth 会话（首次认证后自动生成）
│   ├── body_data_*.json    # 身体成分数据本地备份（全量 28 项）
│   ├── captcha/            # 登录验证码图片（触发验证码时自动生成）
│   └── garmin-fit/         # 生成的 FIT 文件
├── tests/              # 测试（unittest）
├── debug/              # 调试脚本（原始数据导出等）
├── users.json          # 核心配置文件（无密：只存账号/邮箱等身份，不含密码和 token）
├── requirements.txt    # 运行依赖
├── requirements-gui.txt    # GUI 依赖（PyQt6 等）
├── requirements-build.txt  # 打包依赖（PyInstaller 等）
├── build.py            # 打包脚本（生成 GUI/CLI 可执行文件）
├── pyi_rth_pyqt6.py    # PyInstaller PyQt6 运行时钩子
├── Dockerfile          # Docker 镜像定义
├── docker-compose.yml  # Docker 服务编排（login / sync）
└── README.md
```

### 前置条件

- **Python 3.12.x**：[官网下载](https://www.python.org/downloads/)。3.14 不兼容，请勿使用。
- 安装时勾选 **"Add Python to PATH"**。
- 验证：

```bash
python --version
```

输出 `Python 3.12.x` 即可。

---

## 2. 下载与安装

```bash
# 克隆仓库（或在仓库页面点 Code → Download ZIP 后解压）
git clone git@github.com:zeronesun/mi-scale-to-garmin.git
cd mi-scale-to-garmin

# 创建并激活虚拟环境（隔离项目依赖，推荐）
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Mac/Linux:
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

---

## 2.5. Docker 部署

> ⚠️ **当前不可用**：镜像 `zeronesun/mi-scale-to-garmin` 尚未构建发布（仓库创建与 CI 发布进行中），`docker-compose pull` 会 404。当前请使用上面的 Python 方式部署；镜像就绪后本节自动生效。

不需要本地 Python 环境时可用 Docker 部署。前提：已安装 [Docker Desktop](https://www.docker.com/products/docker-desktop)（Windows/Mac）或通过 `curl -fsSL https://get.docker.com | sh` 安装（Linux），`docker --version` 可输出版本号。

完整流程、目录结构与排错见 [docs/DOCKER_SETUP.md](docs/DOCKER_SETUP.md)。核心命令：

```bash
git clone git@github.com:zeronesun/mi-scale-to-garmin.git
cd mi-scale-to-garmin
cp config/users.json.example config/users.json   # 模板含 // 注释，复制后需删除
docker-compose pull
docker-compose --profile login run --rm login    # 首次：小米授权
docker-compose run --rm sync                     # 同步
```

---

## 3. 配置

`users.json` 是程序唯一的配置文件。若不存在，复制 `config/users.json.example` 为 `users.json`（模板含 `//` 注释，复制后需删除注释行使其成为合法 JSON）。

**`users.json` 只存身份、偏好、体脂秤型号，不含密码、不含 token**，可安全备份/分享。

```json
{
    "users": [
        {
            "xiaomi_prefix": "my_xiaomi",
            "username": "您的手机号/邮箱",
            "model": "yunmai.scales.ms103",
            "garmin_prefix": "my_garmin",
            "garmin": {
                "email": "您的佳明账号",
                "domain": "CN"
            }
        }
    ]
}
```

### 参数说明

| 参数 | 说明 |
|------|------|
| `username` / `garmin.email` | 账号身份。留空时程序首次运行会引导式提示输入并写回。 |
| `xiaomi_prefix` / `garmin_prefix` | 脱敏标识（可选），用于输出文件名、会话目录和日志。不填则回退到账号 SHA256 前 8 位，**永不使用明文账号**。 |
| `model` | 设备型号。小米体脂秤 S400 填 `yunmai.scales.ms103`；数据已导入小米运动健康时保持默认即可。 |
| `garmin.domain` | 佳明服务器区域。中国区 `CN`，国际区（台/港/美等）`COM`。 |
| 密码与 token | 密码仅在认证时终端输入（隐藏回显），认证后丢弃、不落盘；token 自动存到 `data/xiaomi_auth_{prefix}.json`（小米）和 `data/.garth/{prefix}/`（佳明），下次运行自动复用。 |

---

## 4. 使用

### 一键同步

```bash
# 拉取数据、生成 FIT 文件、自动上传佳明
python src/main.py --config users.json --sync
```

**首次运行**会按需在终端引导完成认证（之后不再询问）：

1. **身份补齐**：`users.json` 中留空的账号/邮箱会提示输入并写回。
2. **小米认证**：输入小米密码（隐藏回显）；开启二次验证的账号需输入 6 位短信验证码。成功后 token 存到 `data/xiaomi_auth_{prefix}.json`。
3. **佳明认证**：上传前输入佳明密码（隐藏回显）。成功后会话存到 `data/.garth/{prefix}/`。

**后续运行**：token/会话有效时全程零交互。

同步执行流程：

1. 登录小米（复用已存 token，失效时引导重新认证）。
2. 拉取**全部**历史身体成分记录（双源合并：旧 API 实时数据 + 新 API 补充 Zeeplife 导入数据），终端默认显示最近 10 条（`--limit` 调整显示条数，不影响实际拉取与上传）。
3. 本地备份到 `data/body_data_{脱敏标识}.json`。
4. 在 `data/garmin-fit/` 生成 FIT 文件。
5. 登录佳明（复用已存会话）并上传。

### 单独认证（不同步）

`src/xiaomi/login.py` 是独立的小米认证工具，适合只刷新/验证小米 token、不跑同步的场景：

```bash
python src/xiaomi/login.py --config users.json
```

- 流程与 `--sync` 内部一致（身份补齐 → 密码 → 2FA → token 落盘），两边 token 互通复用。
- 只管小米侧；佳明认证在上传时才需要（会话有效则不询问）。
- 小米认证有账号风控风险，token 有效时不必反复运行。

---

## 5. 进阶

### 命令行参数

| 参数 | 说明 |
|------|------|
| `--config PATH` | 配置文件路径（默认 `users.json`） |
| `--limit N` | 终端显示最近多少条记录（默认 10，不影响实际拉取） |
| `--fit` | 仅生成本地 FIT 文件，不上传 |
| `--sync` | 生成并上传（一键同步模式） |
| `--output-dir PATH` | FIT 输出目录（默认 `data/garmin-fit`） |
| `--non-interactive` | 非交互模式，需要输入时直接报错退出（计划任务/CI 用；token 有效时不受影响） |

### 图形界面（可选）

```bash
pip install -r requirements-gui.txt   # 含 PyQt6 等 GUI 依赖
python src/gui/main.py users.json     # 配置文件路径为位置参数（默认 users.json）
```

GUI 支持多用户管理、同步进度显示、密码弹窗输入；认证流程与 CLI 相同（首次需完成认证）。

### 定时自动同步

```bash
# Linux/Mac：cron，每天凌晨 2 点（--non-interactive：无人值守，需要输入时直接报错而不是卡住）
0 2 * * * cd /项目路径 && .venv/bin/python src/main.py --sync --non-interactive
```

Windows 任务计划程序见 [docs/USAGE.md](docs/USAGE.md#4-自动化运行)。

> 前提：先在终端手动跑过一次 `--sync` 完成认证。token/会话有效期内定时任务零交互；失效时任务报错退出（不会卡死），手动跑一次重新认证即可。

---

## 6. 数据过滤

支持在同步前按健康指标过滤身体成分数据。配置位于每个用户的 `garmin.filter` 下，详见 [docs/FILTER_CONFIG.md](docs/FILTER_CONFIG.md)。

```json
"filter": {
    "enabled": true,
    "conditions": [
        { "field": "Weight", "operator": "between", "value": [60, 70] }
    ],
    "logic": "and"
}
```

- 支持 9 个指标：`Weight`、`BMI`、`BodyFat`、`BodyWater`、`BoneMass`、`MetabolicAge`、`MuscleMass`、`VisceralFat`、`BasalMetabolism`
- 多条件组合（AND/OR 逻辑），每个用户独立配置
- 不配置则同步所有数据；配置非法时跳过过滤并告警，不中断同步

---

## 7. 常见问题 (FAQ)

### Q: 提示 `ModuleNotFoundError: No module named 'requests'`？

依赖未安装或虚拟环境未激活。激活虚拟环境后运行 `pip install -r requirements.txt`。

### Q: 佳明上传一直提示 `Duplicate`？

佳明服务器已存在该记录，属正常去重行为，无需处理。

### Q: 换了新电脑/账号变动？

删除 `data/xiaomi_auth_*.json`（小米认证文件）和 `data/.garth/`（佳明会话目录），重新运行 `python src/main.py --sync` 按提示认证即可。`users.json` 无需改动（不含密码和 token）。

### Q: 支持哪些小米秤？

支持小米运动健康中绑定的所有体脂秤。默认 `model` 无法获取数据时，可在米家/小米运动健康 App 的设备信息中查找到类似 `yunmai.scales.xxx` 的 ID，填入 `model` 字段（见 [docs/USAGE.md](docs/USAGE.md#1-如何查找体脂秤-model-id)）。

---

## 🛡️ 安全说明

- `users.json` 不含密码和 token（仅账号/邮箱等身份信息），仍建议不要公开分享。
- 敏感数据在 `data/` 下：`data/xiaomi_auth_*.json`（小米 token）、`data/.garth/`（佳明 OAuth token）——已 `.gitignore`，**勿以任何方式（含 `git add -f`）提交或分享**。
- 密码仅在认证时终端输入（隐藏回显），认证后丢弃，不落盘。

---

## ✨ 许可证

MIT License

参考项目：

- [XiaomiGateway3](https://github.com/AlexxIT/XiaomiGateway3) — 小米协议
- [garth](https://github.com/matin/garth) — Garmin OAuth 库
- [garmin-weight-sync](https://github.com/XiaoSiHwang/garmin-weight-sync)
- [garmin-connect-plugin-for-dsh](https://github.com/Likenttt/garmin-connect-plugin-for-dsh)
