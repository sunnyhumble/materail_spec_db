#!/bin/bash
#
# Material Spec Database 服务管理脚本
# 使用方法: ./manage_service.sh [start|stop|restart|status]
#

SERVICE_NAME="material_spec_db"
PYTHON_ENV="/home/yb/miniconda3/envs/material_spec/bin/python"
APP_SCRIPT="/home/yb/trae_project/material_spec_db/app.py"
PID_FILE="/tmp/material_spec_db.pid"

# 获取进程 PID
get_pid() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p $PID > /dev/null 2>&1; then
            echo $PID
            return 0
        fi
    fi
    # 如果 PID 文件不存在，尝试通过进程名查找
    PID=$(pgrep -f "$APP_SCRIPT" | head -1)
    if [ -n "$PID" ]; then
        echo $PID
        return 0
    fi
    return 1
}

# 启动服务
start_service() {
    echo "启动 Material Spec Database 服务..."
    cd /home/yb/trae_project/material_spec_db

    # 检查是否已运行
    if get_pid > /dev/null 2>&1; then
        PID=$(get_pid)
        echo "服务已在运行中 (PID: $PID)"
        return 1
    fi

    # 使用 nohup 后台启动
    nohup $PYTHON_ENV $APP_SCRIPT > /tmp/material_spec_db.log 2>&1 &
    NEW_PID=$!
    echo $NEW_PID > "$PID_FILE"

    # 等待服务启动
    sleep 3

    if get_pid > /dev/null 2>&1; then
        PID=$(get_pid)
        echo "服务启动成功 (PID: $PID)"
        return 0
    else
        echo "服务启动失败，请检查日志: /tmp/material_spec_db.log"
        return 1
    fi
}

# 停止服务
stop_service() {
    echo "停止 Material Spec Database 服务..."
    
    if ! get_pid > /dev/null 2>&1; then
        echo "服务未运行"
        return 1
    fi

    PID=$(get_pid)
    
    # 优雅停止 - 发送 SIGTERM
    kill $PID 2>/dev/null
    
    # 等待进程结束
    for i in {1..10}; do
        if ! ps -p $PID > /dev/null 2>&1; then
            rm -f "$PID_FILE"
            echo "服务已停止"
            return 0
        fi
        sleep 1
    done
    
    # 强制杀死进程
    kill -9 $PID 2>/dev/null
    rm -f "$PID_FILE"
    echo "服务已强制停止"
    return 0
}

# 重启服务
restart_service() {
    echo "重启 Material Spec Database 服务..."
    stop_service
    sleep 2
    start_service
}

# 查看状态
status_service() {
    echo "Material Spec Database 服务状态:"
    
    if get_pid > /dev/null 2>&1; then
        PID=$(get_pid)
        echo "  状态: 运行中"
        echo "  PID: $PID"
        
        # 显示启动时间
        if [ -f /proc/$PID/stat ]; then
            START_TIME=$(ps -p $PID -o lstart= 2>/dev/null || echo "未知")
            echo "  启动时间: $START_TIME"
        fi
        
        # 显示端口
        PORT=$(netstat -tlnp 2>/dev/null | grep $PID | awk '{print $4}' | tail -1 || echo "5005")
        echo "  端口: $PORT"
        
        return 0
    else
        echo "  状态: 已停止"
        return 1
    fi
}

# 查看日志
logs_service() {
    echo "最近的日志 (/tmp/material_spec_db.log):"
    if [ -f /tmp/material_spec_db.log ]; then
        tail -n 50 /tmp/material_spec_db.log
    else
        echo "日志文件不存在"
    fi
}

# 主逻辑
case "$1" in
    start)
        start_service
        ;;
    stop)
        stop_service
        ;;
    restart)
        restart_service
        ;;
    status)
        status_service
        ;;
    logs)
        logs_service
        ;;
    *)
        echo "用法: $0 {start|stop|restart|status|logs}"
        exit 1
        ;;
esac

exit $?
