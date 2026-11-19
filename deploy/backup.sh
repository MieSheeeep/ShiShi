#!/usr/bin/env bash
# 食拾生产数据热备份脚本（SQLite + 媒体图片目录）
#
# 用法：
#   chmod +x deploy/backup.sh
#   ./deploy/backup.sh
#
# 定时任务示例（crontab -e，每天凌晨 03:30 自动备份，保留最近 7 天）：
#   30 3 * * * /opt/ShiShi/deploy/backup.sh >> /var/log/shishi-backup.log 2>&1

set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="${SHISHI_DATA_DIR:-${APP_DIR}/data}"
BACKUP_DIR="${SHISHI_BACKUP_DIR:-${APP_DIR}/backups}"
KEEP_DAYS="${SHISHI_BACKUP_KEEP_DAYS:-7}"
STAMP="$(date +%Y%m%d-%H%M%S)"
TARGET_DIR="${BACKUP_DIR}/${STAMP}"

mkdir -p "${TARGET_DIR}"

DB_FILE="${DATA_DIR}/shishi.db"
if [[ -f "${DB_FILE}" ]]; then
  if command -v sqlite3 >/dev/null 2>&1; then
    sqlite3 "${DB_FILE}" ".backup '${TARGET_DIR}/shishi.db'"
  elif docker ps --format '{{.Names}}' 2>/dev/null | grep -qx 'shishi-app'; then
    docker exec shishi-app sqlite3 /app/data/shishi.db ".backup '/tmp/shishi-${STAMP}.db'"
    docker cp "shishi-app:/tmp/shishi-${STAMP}.db" "${TARGET_DIR}/shishi.db"
    docker exec shishi-app rm -f "/tmp/shishi-${STAMP}.db"
  else
    echo "错误：未找到本机 sqlite3 命令，且 shishi-app 容器未运行，无法执行在线热备。" >&2
    exit 1
  fi
else
  echo "警告：未找到数据库文件 ${DB_FILE}，跳过数据库备份。"
fi

if [[ -d "${DATA_DIR}/media" ]]; then
  tar -czf "${TARGET_DIR}/media.tar.gz" -C "${DATA_DIR}" media
fi

# 清理过期备份目录
find "${BACKUP_DIR}" -mindepth 1 -maxdepth 1 -type d -mtime "+${KEEP_DAYS}" -exec rm -rf {} +

echo "[$(date -Iseconds)] 备份完成：${TARGET_DIR}"
