#!/bin/bash

# 部署脚本：将应用部署到新服务器并执行数据库迁移
# 使用方法：./deploy_to_new_server.sh

set -e

echo "=========================================="
echo "应用部署脚本 - 新服务器"
echo "=========================================="

# 激活conda环境
echo "[1] 激活Python环境..."
eval "$(conda shell.bash hook)"
conda activate material_spec

# 检查PostgreSQL连接
echo "[2] 检查PostgreSQL连接..."
PGPASSWORD=12345678 psql -h localhost -U material_spec -d material_spec_db -c "SELECT version();" > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "  ✓ PostgreSQL连接成功"
else
    echo "  ✗ PostgreSQL连接失败，请检查配置"
    exit 1
fi

# 安装依赖
echo "[3] 安装Python依赖..."
pip install psycopg2-binary

# 执行数据迁移
echo "[4] 执行数据库迁移..."
python migrate_to_postgres.py

# 配置systemd服务
echo "[5] 配置systemd服务..."
sudo cp material-spec.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable material-spec

# 启动服务
echo "[6] 启动服务..."
sudo systemctl start material-spec

# 检查服务状态
echo "[7] 检查服务状态..."
sleep 2
systemctl status material-spec --no-pager

echo ""
echo "=========================================="
echo "✓ 部署完成！"
echo "=========================================="
echo ""
echo "访问地址：http://172.26.100.14:5000"
echo ""
echo "常用命令："
echo "  sudo systemctl status material-spec  - 查看状态"
echo "  sudo systemctl restart material-spec - 重启服务"
echo "  sudo systemctl stop material-spec    - 停止服务"
echo "  ./manage-service.sh logs             - 查看日志"
