# docker/ — Docker 镜像与编排

本目录集中存放 Docker 相关配置。镜像构建上下文为**项目根目录**（Dockerfile 内 `COPY` 的路径均相对项目根）。

## 文件

| 文件 | 用途 |
|------|------|
| `Dockerfile` | 镜像定义（python:3.12.6-slim，安装 `requirements/runtime.txt` + 拷贝 `src/`） |
| `docker-compose.yml` | 服务编排：`login`（首次认证，profile）+ `sync`（周期同步） |

## 常用命令

```bash
# 构建镜像（-f 指定 Dockerfile，上下文为项目根）
docker build -f docker/Dockerfile -t mi-scale-to-garmin .

# 首次认证（交互式，输入小米账号密码）
docker compose -f docker/docker-compose.yml --profile login run --rm login

# 周期同步
docker compose -f docker/docker-compose.yml run --rm sync
```

> `docker-compose.yml` 中的卷挂载（`../config`、`../data`）相对本文件所在目录解析，指向项目根的 `config/` 和 `data/`。

## 发布

- 镜像仓库：Docker Hub `zeronesun/mi-scale-to-garmin`
- 推送由 CI 完成：`.github/workflows/docker-publish.yml`（tag `v*.*.*` 触发，多平台 linux/amd64 + arm64）
- 本地推送（需 Docker Hub 登录）：`docker tag` + `docker push`
- 详细部署说明见 [docs/DOCKER_SETUP.md](../docs/DOCKER_SETUP.md)
