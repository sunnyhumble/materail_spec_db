# Systemd 服务管理指南

## 概述

Material Spec Database System 已配置为 systemd 服务，可以通过 systemd 命令或管理脚本来控制。

**服务名称**: `material-spec`  
**端口**: 5005  
**工作目录**: `/home/yb/material_spec_db`

## 快速开始

### 1. 安装服务（首次使用）

```bash
# 复制服务文件到 systemd 目录并注册
sudo ./manage-service.sh install
```

### 2. 启动服务

```bash
# 使用管理脚本
sudo ./manage-service.sh start

# 或直接使用 systemctl
sudo systemctl start material-spec
```

### 3. 设置开机自启

```bash
# 使用管理脚本
sudo ./manage-service.sh enable

# 或直接使用 systemctl
sudo systemctl enable material-spec
```

## 服务管理命令

### 基本操作

| 操作 | 管理脚本命令 | systemctl 命令 |
|------|------------|--------------|
| 启动 | `sudo ./manage-service.sh start` | `sudo systemctl start material-spec` |
| 停止 | `sudo ./manage-service.sh stop` | `sudo systemctl stop material-spec` |
| 重启 | `sudo ./manage-service.sh restart` | `sudo systemctl restart material-spec` |
| 状态 | `./manage-service.sh status` | `systemctl status material-spec` |
| 启用 | `sudo ./manage-service.sh enable` | `sudo systemctl enable material-spec` |
| 禁用 | `sudo ./manage-service.sh disable` | `sudo systemctl disable material-spec` |

### 查看日志

```bash
# 查看最近 50 行日志
./manage-service.sh logs

# 实时查看日志（Ctrl+C 退出）
./manage-service.sh live-logs

# 使用 journalctl 查看日志
journalctl -u material-spec -n 50 --no-pager
journalctl -u material-spec -f
```

## Systemd 服务配置说明

服务文件位置：`/etc/systemd/system/material-spec.service`

主要配置项：
- **WorkingDirectory**: `/home/yb/material_spec_db`
- **ExecStart**: `/home/yb/anaconda3/envs/material_spec_db/bin/python /home/yb/material_spec_db/app.py`
- **Restart**: `on-failure` (失败时自动重启)
- **RestartSec**: `5` (重启间隔 5 秒)
- **端口**: 5005 (在 app.py 中配置)

## 常见问题排查

### 1. 检查服务状态

```bash
systemctl status material-spec
```

### 2. 查看错误日志

```bash
# 查看最近的错误日志
journalctl -u material-spec -p err -n 50

# 查看今天的所有日志
journalctl -u material-spec --since today
```

### 3. 重启服务

```bash
sudo systemctl restart material-spec
```

### 4. 重新加载 systemd 配置

如果修改了服务文件，需要重新加载：

```bash
sudo systemctl daemon-reload
```

### 5. 检查端口占用

```bash
# 查看 5005 端口是否被占用
lsof -i :5005
```

## 开机自启

服务已启用开机自启后，系统重启时会自动启动：

```bash
# 确认服务已启用
systemctl is-enabled material-spec

# 如果未启用，执行：
sudo systemctl enable material-spec
```

## 服务文件更新流程

1. 修改 `/home/yb/material_spec_db/material-spec.service`
2. 重新安装服务：
   ```bash
   sudo ./manage-service.sh install
   ```
3. 重启服务：
   ```bash
   sudo ./manage-service.sh restart
   ```

## 安全特性

服务配置包含以下安全增强：
- **NoNewPrivileges=true**: 禁止获取新权限
- **PrivateTmp=true**: 使用私有临时目录
- **StandardOutput/StandardError=journal**: 日志集中管理

## 环境变量

服务运行时设置的环境变量：
- `PATH`: 包含 conda 环境的路径
- `PYTHONUNBUFFERED=1`: Python 输出不缓冲（便于日志查看）

## 联系支持

如有问题，请查看日志或联系系统管理员。
