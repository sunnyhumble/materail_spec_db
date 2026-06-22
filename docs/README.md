# 金属材料规范数据库系统

## 项目概述

金属材料规范数据库系统是一个基于 Web 的材料规范数据管理平台，用于存储、查询和管理金属材料的各项性能规范数据。系统支持通过图片识别方式自动提取材料规范表格数据，大幅提升数据录入效率。

## 系统功能

### 1. 数据查询
- 多条件组合查询：编号、牌号、状态、类别、取样方向
- 支持模糊匹配和精确查询
- 分页展示查询结果

### 2. 手工录入
- 表单方式手动添加材料规范
- 根据选择的测试类别动态显示对应字段
- 支持数据编辑和删除

### 3. 图片识别
- 上传材料规范表格图片
- 调用大模型 API 自动识别提取数据
- 支持识别结果预览和编辑
- 批量导入识别数据到数据库

### 4. 字段管理
- 管理测试类别和字段定义
- 支持动态添加、修改、删除类别和字段

### 5. 数据统计
- 规范总数统计
- 合金牌号数量统计
- 测试类别数量统计

## 数据模型

### 必填字段

每条材料规范数据包含以下必填字段：

| 字段 | 说明 | 示例 |
|------|------|------|
| 编号 | 文件编号 | GJB 2351A-2021 |
| 类别 | 测试类别 | 拉伸、冲击、硬度等 |
| 牌号 | 材料牌号 | 2A12、TC4 |
| 状态 | 材料状态 | T6-模锻件、固溶态 |
| 规格 | 产品规格 | δ≤10mm、φ20mm |
| 取样方向 | 取样方向 | 纵向、横向、高向 |

### 测试类别与字段

系统预置 11 种测试类别：

| 类别代码 | 类别名称 | 字段 |
|----------|----------|------|
| chemical_composition | 化学成分 | C, Cr, Mo, Al, Ti, Co, B, Ni, Si, Mn, S, P, Zr, Cu, Fe, Pb, As, Sn, Sb, Bi, Ag |
| tension | 拉伸 | 试验温度、抗拉强度、屈服强度、规定塑性延伸强度、上屈服强度、下屈服强度、断后伸长率、断面收缩率 |
| impact | 冲击 | 试验温度、冲击吸收能量 |
| stress_rupture | 持久 | 试验温度、应力、持久时间、断面收缩率 |
| creep | 蠕变 | 试验温度、应力、蠕变伸长率、蠕变断面收缩率 |
| macro_structure | 宏观组织 | 要求描述 |
| fracture_inspection | 断口检验 | 要求描述 |
| grain_size | 晶粒度 | 要求描述 |
| non_metallic_inclusion | 非金属夹杂 | 要求描述 |
| microstructure | 显微组织 | 要求描述 |
| hardness | 硬度 | 硬度类型、标尺、硬度值 |

## 技术架构

### 后端
- **Web 框架**: Flask 2.x
- **数据库**: SQLite（轻量级，无需额外安装）
- **ORM**: SQLAlchemy 2.x
- **图片解析**: OpenAI API (GPT-4o)

### 前端
- **UI 框架**: Bootstrap 5.1
- **图标**: Bootstrap Icons
- **交互**: 原生 JavaScript (ES6+)

### 目录结构

```
material_spec_db/
├── app.py                 # Flask 主程序
├── config.py              # 配置文件
├── requirements.txt       # Python 依赖
├── material_specs.db      # SQLite 数据库文件
├── database/
│   ├── __init__.py
│   ├── models.py         # 数据库模型
│   └── operations.py     # 数据库操作
├── parser/
│   ├── __init__.py
│   └── llm_parser.py    # 图片解析模块
├── templates/
│   └── index.html        # 前端页面
├── docs/
│   ├── README.md         # 使用说明
│   ├── DEPLOYMENT.md     # 部署指南
│   └── DATA_STRUCTURE.md # 数据结构文档
└── material-spec.service # systemd 服务文件
```

## 部署要求

### 硬件要求
- CPU: 2 核及以上
- 内存: 4GB 及以上
- 磁盘: 10GB 及以上

### 软件要求
- 操作系统: Ubuntu 20.04 / Windows 10+
- Python: 3.8 及以上
- 网络: 访问大模型 API（需要互联网连接）

## 使用流程

### 1. 配置 API 密钥
编辑 `.env` 文件，配置大模型 API 密钥：
```bash
OPENAI_API_KEY=your-api-key-here
```

### 2. 启动服务
```bash
pip install -r requirements.txt
python app.py
```

### 3. 访问系统
打开浏览器访问 `http://localhost:5005`

## 扩展说明

### 添加新的测试类别
系统支持动态添加新的测试类别，通过字段管理界面或代码实现。

### 更换大模型
系统支持多种大模型 API，包括：
- OpenAI GPT-4o
- 月之暗面 Moonshot
- 阿里云通义千问
- 其他 OpenAI 兼容的 API

修改 `config.py` 中的 `API_BASE_URL` 和 `API_MODEL` 即可切换。

## 注意事项

1. **数据备份**: 定期备份 `material_specs.db` 数据库文件
2. **API 费用**: 图片识别功能会产生 API 调用费用
3. **网络安全**: 建议在生产环境中配置 HTTPS
4. **并发访问**: SQLite 不支持高并发写入，如需高并发请考虑迁移到 MySQL/PostgreSQL

## 许可证

本项目仅供学习和企业内部使用。
