# 使用与排错

README 未覆盖的细节问题都在这里。首次使用请先读 [README.md](../README.md)。

---

## 1. 如何查找体脂秤 Model ID

默认型号为 `yunmai.scales.ms103`（小米体脂秤 S400）。其他型号或默认值拉不到数据时，按以下步骤查找：

1. 打开**米家 (Mi Home)** 或**小米运动健康 (Mi Fitness)** App。
2. 进入体脂秤设备页面。
3. 点击右上角三个点（设置）。
4. 在"关于设备"或"网络信息"中找到类似 `yunmai.scales.xxx` 的字符串。
5. 填入 `users.json` 的 `model` 字段。

---

## 2. 佳明账号区服 (domain)

佳明中国服务器 (Garmin.cn) 与国际站完全独立，区服填错会导致认证失败：

- **Garmin.cn 注册的账号** → `domain: "CN"`
- **国际站账号** → `domain: "COM"`

验证方法：浏览器访问 [Connect.garmin.cn](https://connect.garmin.cn)，能登录即为国内区；提示跳转国际站则为海外区。

---

## 3. 登录报错排查

### 3.1 验证码图片打不开

`login.py` 运行后浏览器未自动弹出或图片加载失败时：查看终端输出中的图片保存路径（如 `data/captcha/captcha_<时间戳>.png`），手动打开该图片输入验证码。

### 3.2 2FA (二次验证) 失败

- 确认小米账号绑定的手机号能正常接收短信。
- 验证码有效期 5-10 分钟，收到后尽快输入。

---

## 4. 自动化运行

前提：已手动跑过一次 `--sync` 完成认证（见 [README 定时自动同步](../README.md#5-进阶)）。

### Windows（任务计划程序）

1. `Win + R` → `taskschd.msc` 打开任务计划程序。
2. 右侧"创建基本任务"，名称如 `Xiaomi-Garmin-Sync`，触发器选"每天"。
3. 操作选"启动程序"：
   - **程序/脚本**：`C:\你的路径\.venv\Scripts\python.exe`
   - **添加参数**：`C:\你的路径\src\main.py --sync --non-interactive`
   - **起始于**：项目根目录路径

### Mac/Linux（crontab）

```bash
crontab -e
# 每天 08:00 同步（--non-interactive：无人值守，token 失效时报错退出而非卡住）
0 8 * * * /Users/你的用户名/项目路径/.venv/bin/python /Users/你的用户名/项目路径/src/main.py --sync --non-interactive
```

---

## 5. 数据目录在哪里

排错时先确认数据落点（完整规则见 [README 2.6 节](../README.md#26-数据目录规则)）：

| 运行形态 | 数据目录 |
|----------|----------|
| 开发版（`python src/main.py`） | 项目根 `data/` |
| 打包版 exe（CLI / GUI） | Windows `%APPDATA%\mi-scale-to-garmin\`；macOS `~/Library/Application Support/mi-scale-to-garmin/`；Linux `~/.local/share/mi-scale-to-garmin/` |
| Docker | 容器内 `/app/data`（volume 挂载） |

- 本文档中出现的 `data/...` 路径，打包版请替换为上述实际数据目录。
- **`users.json` 位置**：开发版在项目根；打包版在数据目录内（`%APPDATA%\mi-scale-to-garmin\users.json`）。
- 开发版与打包版 token 和配置不共享，两种形态各认证一次。
- GUI 可在"设置 → 数据目录设置"中查看当前目录、自定义或重置为默认。

---

## 6. 高级排错

### 6.1 查看详细状态

同步失败但无明确报错时，按数据流逐段定位：

- `data/body_data_{脱敏标识}.json` **已生成**但佳明无数据 → 问题在佳明授权或网络侧。
- `body_data` 未生成 → 问题在小米侧（token 失效/网络/型号），查看终端日志。
- 终端日志中 `登录成功` / `token 已保存` 表示认证环节通过。

### 6.2 重置认证（环境重置）

顽固授权问题的标准重置流程：

1. 删除 `data/xiaomi_auth_*.json`（小米凭证）和 `data/.garth/`（佳明会话缓存）。
2. 重新运行 `python src/main.py --sync`，按提示重新认证。
3. `users.json` 无需改动（不含密码和 token）。

---

## 7. 反馈与贡献

发现 Bug 或有改进建议，欢迎通过 GitHub Issues / PR 反馈。
