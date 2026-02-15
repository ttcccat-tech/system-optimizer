# System Optimizer

系統優化工具集 - 用於監控和優化 OpenClaw 部署環境。

## 工具列表

### 1. health_check.py
系統健康檢查工具，定期檢查以下指標：

- **磁碟使用情況**：檢查根分區使用率
- **記憶體使用情況**：監控 RAM 使用量
- **系統負載**：檢查 1/5/15 分鐘平均負載
- **Docker 容器狀態**：檢查所有容器運行狀態
- **OpenClaw 狀態**：檢查 OpenClaw 進程是否運行
- **Agent Sessions 大小**：監控 session 數據大小

#### 使用方法

```bash
python3 health_check.py
```

輸出格式：JSON

```json
{
  "timestamp": "2026-02-15T18:02:21.379292",
  "checks": {
    "disk": {...},
    "memory": {...},
    "load": {...},
    "docker": {...},
    "openclaw": {...},
    "agent_sessions": {...}
  },
  "overall": {
    "status": "healthy|warning|error",
    "warnings": [...],
    "errors": [...]
  }
}
```

#### 設置為 Cron 任務

每晚 2:00 AM 執行健康檢查：

```bash
# 編輯 crontab
crontab -e

# 添加以下行
0 2 * * * /usr/bin/python3 /home/user/repo/system-optimizer/health_check.py >> /var/log/health_check.log 2>&1
```

## Worker Dashboard 優化

### Gunicorn 配置

Worker Dashboard 已配置使用 Gunicorn 作為 production WSGI server：

- **配置文件**：`gunicorn_config.py`
- **Dockerfile**：`Dockerfile.gunicorn`
- **Worker 數量**：自動根據 CPU 核心數調整
- **超時設定**：30 秒

#### 使用 Gunicorn 重建容器

```bash
cd /home/user/docker/worker-dashboard

# 停止現有容器
docker-compose down

# 使用新的 Dockerfile 重建
docker build -f Dockerfile.gunicorn -t worker-dashboard-web .

# 啟動容器
docker-compose up -d
```

## 優化記錄

### 2026-02-15

1. **健康檢查工具**
   - 創建 `health_check.py` 系統監控工具
   - 檢查 6 個關鍵系統指標
   - 生成 JSON 格式報告

2. **Worker Dashboard 優化**
   - 創建 Gunicorn 配置文件
   - 添加 production-ready Dockerfile
   - 自動調整 worker 數量（CPU cores * 2 + 1）

3. **系統狀態**
   - 磁碟使用率：9% (健康)
   - 記憶體使用：2.2Gi / 7.8Gi (健康)
   - 系統負載：0.26 (健康)
   - Docker 容器：1/1 運行中 (健康)
   - OpenClaw：運行中 (PID 832)
   - Agent Sessions：616K (健康)

## 待辦事項

- [ ] 添加日誌輪轉配置
- [ ] 設置警報通知 (當系統狀態為 warning/error 時)
- [ ] 創建 Web Dashboard 可視化健康狀態
- [ ] 添加性能趨勢分析
- [ ] 配置自動清理舊的 session 文件
