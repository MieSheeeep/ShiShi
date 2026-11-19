# 华为云最小上线部署指南

本文档面向单机轻量部署场景：使用 **1 台华为云主机 + Docker Compose + Caddy** 运行食拾（FastAPI 托管前端构建产物，SQLite 存储数据，本地磁盘保存图片）。

## 1. 服务器选型建议

- **机型**：华为云 **云耀云服务器 L 实例（HECS L）** 或 **弹性云服务器 ECS**
- **配置**：`2核 2G`（够用，建议开启 2G Swap 防构建内存不足）或 `2核 4G`（推荐，直接 `docker compose build` 更宽裕）
- **系统**：Ubuntu 22.04 / 24.04 LTS，系统盘 40GB 起
- **安全组入方向规则**：仅放行 `22`（SSH）、`80`（HTTP）、`443`（HTTPS），不要对外开放 `8000` 端口

> **域名与备案提示**：
> - 若选择**中国大陆节点**并绑定域名访问 80/443，必须先完成 ICP 备案。
> - 若暂未备案或仅做短期体验，可先不绑域名（`SHISHI_SITE_ADDRESS=:80`，通过 `http://<公网IP>` 访问），或选择**香港 / 新加坡节点**免备案绑定域名。

## 2. 安装 Docker 与准备代码

```bash
# 安装 Docker 与 Docker Compose 插件（Ubuntu）
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker "$USER"
# 重新登录 SSH 使 docker 组生效

# 拉取仓库
sudo mkdir -p /opt && sudo chown "$USER:$USER" /opt
cd /opt
git clone https://github.com/MieSheeeep/ShiShi.git
cd ShiShi
```

## 3. 配置生产环境变量

```bash
cp deploy/env.example .env
nano .env
```

上线前至少确认以下几项：

| 变量 | 说明 | 生产建议 |
| --- | --- | --- |
| `SHISHI_SITE_ADDRESS` | 站点域名或监听端口 | 无域名填 `:80`；已解析域名填 `shishi.example.com`（Caddy 自动申请免费 HTTPS） |
| `SHISHI_SQLITE_JOURNAL_MODE` | SQLite 日志模式 | 保持 `WAL`，防止断电或进程崩溃损库 |
| `SHISHI_ALLOW_REGISTER` | 是否开放注册 | 公开/熟人共用可保持 `true`；仅自己用可在建完账号后改为 `false` |
| `SHISHI_INVITE_CODE` | 注册邀请码 | **公网上线强烈建议设置**，留空则允许任何人注册 |
| `SHISHI_ALLOW_PRIVATE_AI_URL` | 是否允许 AI Base URL 指向内网 | 保持 `false`，禁止探测 `127.0.0.1`、内网及华为云元数据 `169.254.169.254` |

`.env` 已在 `.gitignore` 中排除，不会提交到仓库。

## 4. 构建并启动服务

```bash
docker compose up -d --build
```

检查容器状态与健康探针：

```bash
docker compose ps
curl -s http://127.0.0.1/api/health
# 预期返回：{"status":"ok","journal_mode":"WAL"}
```

查看运行日志：

```bash
docker compose logs -f shishi caddy
```

## 5. 定时热备份与恢复

仓库提供 `deploy/backup.sh`，使用 `sqlite3 .backup` 在线热备数据库并归档 `data/media/`，默认保留最近 7 天。

```bash
chmod +x /opt/ShiShi/deploy/backup.sh
# 先手动演练一次
/opt/ShiShi/deploy/backup.sh

# 添加每天凌晨 03:30 的定时任务
crontab -e
# 写入以下一行：
# 30 3 * * * /opt/ShiShi/deploy/backup.sh >> /var/log/shishi-backup.log 2>&1
```

**恢复步骤**：

```bash
cd /opt/ShiShi
docker compose stop shishi
# 替换 <时间戳> 为 backups/ 下的目录名
cp backups/<时间戳>/shishi.db data/shishi.db
rm -f data/shishi.db-wal data/shishi.db-shm
rm -rf data/media && tar -xzf backups/<时间戳>/media.tar.gz -C data
docker compose start shishi
```

## 6. 日常更新与上线后检查

更新代码并重建容器（`./data` 目录挂载在宿主机，重建不会丢失数据）：

```bash
cd /opt/ShiShi
/opt/ShiShi/deploy/backup.sh
git pull --ff-only origin main
docker compose up -d --build
```

上线后建议实测：
1. 注册 / 邀请码拦截、登录、修改密码与退出登录。
2. 豆果链接与小红书链接导入（云主机机房 IP 比家庭宽带更容易触发风控，若目标站返回验证页或超时，可改用手动录入或后续接入正文智能提取）。
3. 确认 `curl http://127.0.0.1/api/health` 正常返回且 `backups/` 目录按期生成备份。
