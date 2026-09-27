# Docker 部署

> ⚠️ **当前不可用**：镜像 `zeronesun/mi-scale-to-garmin` 尚未构建发布（仓库创建与 CI 发布进行中），`docker compose pull` 会 404。镜像就绪后本文档自动生效，当前请使用 README 中的 Python 部署方式。

---

## 前置要求

已安装 Docker：

- **Windows / Mac**：[Docker Desktop](https://www.docker.com/products/docker-desktop) 下载安装，首次启动需等待几分钟。
- **Linux**：

```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
# 将当前用户加入 docker 组，免 sudo
sudo usermod -aG docker $USER
newgrp docker
```

验证：

```bash
docker --version
docker compose version
```

---

## 部署流程

### 1. 获取代码

```bash
git clone git@github.com:zeronesun/mi-scale-to-garmin.git
cd mi-scale-to-garmin
```

不会用 git 时，在仓库页面点 `Code` → `Download ZIP`，解压后进入该目录。

### 2. 创建配置文件

`config/` 与 `data/` 由程序自动创建。只需准备配置：

```bash
# Linux/Mac
cp config/users.json.example config/users.json
# 模板含 // 注释，不是合法 JSON，复制后必须删除所有 // 注释行
# Windows：文件管理器中复制一份并重命名，同样删除注释行
```

编辑 `config/users.json`，填写账户信息（无密：不含密码和 token）：

```json
{
    "users": [
        {
            "xiaomi_prefix": "my_xiaomi",
            "username": "您的手机号或邮箱",
            "model": "yunmai.scales.ms103",
            "garmin_prefix": "my_garmin",
            "garmin": {
                "email": "您的佳明账号邮箱",
                "domain": "CN"
            }
        }
    ]
}
```

| 参数 | 说明 | 示例值 |
|------|------|--------|
| `username` | 小米账号手机号或邮箱（留空则首次运行时引导输入） | 您的真实账号 |
| `xiaomi_prefix` / `garmin_prefix` | 脱敏标识（可选），用于文件名/日志；不填回退账号哈希前 8 位 | `my_xiaomi` |
| `model` | 设备型号，小米体脂秤 S400 填此项 | `yunmai.scales.ms103` |
| `garmin.domain` | 佳明服务器区域 | 中国区 `CN`，国际区 `COM` |

密码仅在首次认证时终端输入（隐藏回显），不落盘；token 自动存到 `data/` 下。

### 3. 拉取镜像

```bash
docker compose -f docker/docker-compose.yml pull
```

首次拉取需从 Docker Hub 下载，耗时取决于网络。

### 4. 首次登录（小米授权）

小米账号需验证码登录，首次必须单独运行登录服务：

```bash
docker compose -f docker/docker-compose.yml --profile login run --rm login
```

流程：

1. `config/users.json` 账号/邮箱留空时，先引导式提示输入并写回。
2. 提示输入小米密码（隐藏回显，不落盘）。
3. 图形验证码会自动在浏览器打开，也可手动打开终端输出的图片路径（`data/captcha/captcha_<时间戳>.png`）。
4. 开启 2FA 的账号输入 6 位短信验证码。
5. 成功后 token 存到 `data/auth/xiaomi_auth_*.json`（不进配置文件）。

终端出现登录成功提示后，此步骤只需执行一次。

### 5. 执行同步

```bash
docker compose -f docker/docker-compose.yml run --rm sync
```

执行流程：复用 token 登录小米 → 拉取身体成分数据（终端默认显示最近 10 条）→ 生成 FIT 文件（`data/fit/`）→ 登录佳明并上传 → 备份全量数据（`data/body/body_data_*.json`）。

成功输出示例：

```bash
✅ 批次 1/1 上传成功
📊 上传汇总 - my_xiaomi
  总批次数: 1
  ✅ 成功: 1
  ℹ️ 重复: 0
  ❌ 失败: 0
```

### 6. 查看产物

```bash
ls data/fit/               # 生成的 FIT 文件
ls data/body/              # 数据备份
```

---

## 定时自动同步（可选）

前提：已手动跑过一次登录和同步完成认证。

### Windows（任务计划程序）

1. `Win + R` → `taskschd.msc`，右侧"创建基本任务"。
2. 名称如 `mi-scale-to-garmin`，触发器选"每天"并设置时间。
3. 操作选"启动程序"：
   - **程序或脚本**：`docker`（新版 Docker Desktop 已整合 compose；旧版用 `docker-compose`）
   - **添加参数**：`compose -f docker/docker-compose.yml run --rm sync`
   - **起始于**：项目完整路径（如 `D:\mi-scale-to-garmin`）

### Linux/Mac（crontab）

```bash
crontab -e
# 每天凌晨 2 点，日志追加到 data/sync.log
0 2 * * * cd /项目完整路径 && docker compose -f docker/docker-compose.yml run --rm sync >> /项目完整路径/data/sync.log 2>&1
```

crontab 时间格式：

```bash
┌───────────── 分钟 (0-59)
│ ┌───────────── 小时 (0-23)
│ │ ┌───────────── 日 (1-31)
│ │ │ ┌───────────── 月 (1-12)
│ │ │ │ ┌───────────── 星期 (0-7，0 和 7 均为周日)
* * * * * 要执行的命令
```

常见写法：`0 2 * * *`（每天 2 点）、`0 */6 * * *`（每 6 小时）、`0 8,20 * * *`（每天 8 点和 20 点）。

> 注意：cron 环境不加载 shell 配置，若 `docker` 不在 cron 的 PATH 中，先用 `which docker` 查真实路径并写进绝对路径（新版 Docker 已整合 compose，用 `docker compose`；`docker-compose` 独立版同理查 `which docker-compose`）。

---

## 命令速查

| 操作 | 命令 |
|------|------|
| 拉取镜像 | `docker compose -f docker/docker-compose.yml pull` |
| 首次登录 | `docker compose -f docker/docker-compose.yml --profile login run --rm login` |
| 执行同步 | `docker compose -f docker/docker-compose.yml run --rm sync` |
| 查看日志 | `docker compose -f docker/docker-compose.yml logs sync` |
| 停止所有容器 | `docker compose -f docker/docker-compose.yml down` |

---

## 目录结构

```bash
mi-scale-to-garmin/
├── config/
│   ├── users.json          # 配置文件（无密：只存身份，不含密码和 token）
│   └── users.json.example  # 配置模板（含 // 注释，复制后需删除）
├── data/                   # 运行产物（已 gitignore）
│   ├── auth/               # 凭证（敏感，删除=重置认证）
│   │   ├── xiaomi_auth_*.json  # 小米认证凭证（首次认证后自动生成）
│   │   └── garmin/         # 佳明 OAuth 会话（首次认证后自动生成）
│   ├── body/               # 数据备份（body_data_*.json）
│   ├── fit/                # 生成的 FIT 文件
│   ├── captcha/            # 登录验证码图片（触发验证码时自动生成）
│   └── sync.log            # 定时任务日志（如设置）
├── src/                    # 源代码
└── docker/                 # Docker 配置
    ├── Dockerfile          # 镜像定义（构建上下文为项目根）
    └── docker-compose.yml  # 服务编排（login / sync 两个服务）
```

---

## 常见问题

### Q: `Cannot connect to the Docker daemon`？

Docker Desktop 未启动。启动应用并等待其完全就绪后重试。

### Q: `No such file or directory: config/users.json`？

配置文件未创建，见上文第 2 步。

### Q: 首次登录验证码图片无法打开？

检查浏览器是否正常；也可手动打开终端输出的图片路径（`data/captcha/captcha_<时间戳>.png`）。

### Q: 同步提示 `Duplicate`？

非错误。佳明服务器已存在该记录，程序自动跳过。

### Q: token 过期？

重新运行登录命令：

```bash
docker compose -f docker/docker-compose.yml --profile login run --rm login
```

### Q: Windows 找不到 `docker-compose` 命令？

新版 Docker Desktop 将 compose 整合进了 docker 命令：

```bash
docker compose -f docker/docker-compose.yml run --rm sync
```

（`docker compose` 两个词，非 `docker-compose`；compose 文件在 `docker/` 目录下，需 `-f` 指定）

---

## 安全说明

1. `config/users.json` 不含密码和 token（仅身份信息），仍建议不分享给他人或上传公开站点。
2. 真正的凭证在 `data/auth/` 下（`xiaomi_auth_*.json`、`garmin/`），已 `.gitignore`，**勿以任何方式（含 `git add -f`）提交或分享**。
3. 若凭证不慎泄露，立即修改对应账号密码并删除 `data/` 下相关凭证重新认证。
