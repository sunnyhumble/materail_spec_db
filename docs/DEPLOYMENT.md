# 金属材料规范数据库系统 - 部署指南

本文档详细介绍如何在 Ubuntu 服务器上部署金属材料规范数据库系统。

## 环境要求

| 项目 | 要求 |
|------|------|
| 操作系统 | Ubuntu 20.04 LTS 或更高版本 |
| Python | 3.8 或更高版本 |
| 内存 | 至少 2GB |
| 磁盘 | 至少 5GB 可用空间 |
| 网络 | 需要访问大模型 API（互联网） |

## 部署步骤

### 步骤 1：更新系统并安装依赖

```bash
# 更新系统包
sudo apt update
sudo apt upgrade -y

# 安装 Python 和相关工具
sudo apt install -y python3 python3-pip python3-venv git

# 验证 Python 版本
python3 --version
```

### 步骤 2：创建项目目录

```bash
# 创建项目目录
cd /opt
sudo mkdir -p material-spec-db
cd material-spec-db
```

### 步骤 3：上传项目文件

**方式一：通过 Git 仓库（推荐）**

```bash
git clone <your-repo-url> .
```

**方式二：通过 SCP 上传**

```bash
# 在本地执行，将项目打包上传
scp -r material-spec-db.tar.gz user@your-server-ip:/opt/

# 解压文件
sudo tar -xzf material-spec-db.tar.gz -C /opt/material-spec-db
```

### 步骤 4：配置虚拟环境

```bash
cd /opt/material-spec-db

# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境
source venv/bin/activate

# 升级 pip
pip install --upgrade pip

# 安装依赖
pip install -r requirements.txt
```

### 步骤 5：配置环境变量

```bash
# 复制环境变量示例文件
cp env.example .env

# 编辑配置文件
nano .env
```

在 `.env` 文件中填入您的 API 密钥：

```bash
# OpenAI API 配置
OPENAI_API_KEY=sk-your-api-key-here

# 可选：使用其他 API 服务
# API_BASE_URL=https://api.moonshot.cn/v1
# API_MODEL=moonshot-v1-8k
```

保存并退出（Ctrl+O，回车，Ctrl+X）

### 步骤 6：初始化数据库

```bash
# 激活虚拟环境
source venv/bin/activate

# 启动一次应用以初始化数据库
python3 app.py

# 看到 "Running on http://0.0.0.0:5005" 后，按 Ctrl+C 停止
```

### 步骤 7：配置 systemd 服务

```bash
# 复制服务文件（项目目录中已包含）
sudo cp material-spec.service /etc/systemd/system/

# 重载 systemd
sudo systemctl daemon-reload

# 启动服务
sudo systemctl start material-spec

# 设置开机自启
sudo systemctl enable material-spec

# 查看服务状态
sudo systemctl status material-spec
```

### 步骤 8：配置防火墙

```bash
# 允许 HTTP/HTTPS 和应用端口
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 5005/tcp

# 允许 SSH（如果需要）
sudo ufw allow 22/tcp

# 启用防火墙
sudo ufw enable
```

### 步骤 9：访问系统

部署完成后，通过以下地址访问：

- **直接访问**: `http://your-server-ip:5005`

## 运维操作

### 常用命令

```bash
# 启动服务
sudo systemctl start material-spec

# 停止服务
sudo systemctl stop material-spec

# 重启服务
sudo systemctl restart material-spec

# 查看服务状态
sudo systemctl status material-spec

# 查看日志
sudo journalctl -u material-spec -f
```

### 数据备份

```bash
# 备份数据库
sudo cp /opt/material-spec-db/material_specs.db /backup/material_specs_$(date +%Y%m%d).db

# 或使用 cron 定时备份
sudo crontab -e
# 添加：0 2 * * * cp /opt/material-spec-db/material_specs.db /backup/material_specs_$(date +\%Y\%m\%d).db
```

### 更新应用

```bash
# 停止服务
sudo systemctl stop material-spec

# 进入项目目录
cd /opt/material-spec-db

# 如果使用 Git
git pull

# 激活虚拟环境
source venv/bin/activate

# 更新依赖（如有变化）
pip install -r requirements.txt

# 重启服务
sudo systemctl restart material-spec
```

## 故障排查

### 服务启动失败

```bash
# 查看错误日志
sudo journalctl -u material-spec -n 50
```

常见问题：
1. **端口被占用**: 检查 5005 端口是否被占用 `sudo netstat -tlnp | grep 5005`
2. **权限问题**: 检查目录权限 `sudo chown -R www-data:www-data /opt/material-spec-db`
3. **依赖缺失**: 重新安装依赖 `pip install -r requirements.txt`

### 无法访问服务

```bash
# 检查防火墙
sudo ufw status

# 检查端口监听
sudo netstat -tlnp | grep 5005
```

### 图片识别失败

1. 检查 API 密钥是否正确配置
2. 检查服务器是否能访问外网
3. 查看应用日志中的错误信息

## 安全建议

1. **定期更新系统**: `sudo apt update && sudo apt upgrade`
2. **配置 SSL/HTTPS**: 建议使用 Nginx + Let's Encrypt
3. **限制文件上传**: 当前限制 16MB，可根据需要调整
4. **定期备份**: 建议每日备份数据库
5. **监控服务**: 使用监控工具检查服务运行状态
