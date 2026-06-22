#!/bin/bash

# 快速安装脚本 - 将 material-spec 服务注册到 systemd
# 使用方法：sudo ./install-service.sh

SERVICE_NAME="material-spec"
SERVICE_FILE="/home/yb/material_spec_db/material-spec.service"
SYSTEMD_SERVICE_PATH="/etc/systemd/system/${SERVICE_NAME}.service"

echo "正在安装 material-spec 服务..."

# 复制服务文件
cp "$SERVICE_FILE" "$SYSTEMD_SERVICE_PATH"
if [ $? -ne 0 ]; then
    echo "错误：无法复制服务文件"
    exit 1
fi

# 重新加载 systemd 配置
systemctl daemon-reload

# 启用服务（开机自启）
systemctl enable $SERVICE_NAME

echo ""
echo "✓ 服务安装成功！"
echo ""
echo "现在可以使用的命令："
echo "  sudo systemctl start $SERVICE_NAME     - 启动服务"
echo "  sudo systemctl stop $SERVICE_NAME      - 停止服务"
echo "  sudo systemctl restart $SERVICE_NAME   - 重启服务"
echo "  sudo systemctl status $SERVICE_NAME    - 查看状态"
echo "  sudo systemctl enable $SERVICE_NAME    - 启用开机自启"
echo "  sudo systemctl disable $SERVICE_NAME   - 禁用开机自启"
echo ""
echo "或使用管理脚本："
echo "  sudo ./manage-service.sh start"
echo "  sudo ./manage-service.sh stop"
echo "  sudo ./manage-service.sh restart"
echo "  ./manage-service.sh status"
echo "  ./manage-service.sh logs"
echo ""
echo "要启动服务，请运行：sudo systemctl start $SERVICE_NAME"
