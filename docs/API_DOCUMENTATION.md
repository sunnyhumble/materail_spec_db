# 材料规范数据库查询 API 文档

## 概述

本 API 提供材料规范数据的查询接口，支持按编号、牌号、状态、类别、取样方向、试验条件等条件查询数据。

**API 服务地址**: `http://172.26.100.9:5005`

**API 文档地址**: `http://172.26.100.9:5005/docs` (Swagger UI)

---

## 认证说明

当前版本无需认证，建议在生产环境中根据需要添加 API Key 认证。

---

## 接口列表

### 1. 健康检查

**接口地址**: `GET /`

**说明**: 检查 API 服务是否正常运行，返回 Web 界面

---

### 2. 获取测试类别列表

**接口地址**: `GET /api/categories`

**说明**: 获取所有可用的测试类别

**响应示例**:
```json
{
  "success": true,
  "data": [
    {"id": 1, "name": "化学成分", "code": "chemical_composition", "description": "化学成分分析"},
    {"id": 2, "name": "拉伸", "code": "tension", "description": "拉伸性能测试"},
    {"id": 3, "name": "冲击", "code": "impact", "description": "冲击性能测试"}
  ]
}
```

---

### 3. 获取牌号列表

**接口地址**: `GET /api/alloy-grades`

**说明**: 获取所有已录入的牌号列表

**响应示例**:
```json
{
  "success": true,
  "data": ["23Co14Ni12Cr3MoE", "30Si2MnCrMoVE", "TC4"]
}
```

---

### 4. 获取编号列表

**接口地址**: `GET /api/spec-numbers`

**说明**: 获取所有已录入的规范编号列表

**响应示例**:
```json
{
  "success": true,
  "data": ["11-CL-402B", "GJB 1234-2023", "AMS 1234"]
}
```

---

### 5. 查询材料规范数据 (GET)

**接口地址**: `GET /api/specs`

**说明**: 查询材料规范数据，支持多条件组合查询

**Query 参数**:

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| spec_number | string | 否 | 标准号/编号，**精确匹配** |
| alloy_grade | string | 否 | 牌号，**模糊匹配** |
| status | string | 否 | 状态，**模糊匹配** |
| specification | string | 否 | 规格，精确匹配 |
| sampling_direction | string | 否 | 取样方向，精确匹配 |
| test_category_code | string | 否 | 测试类别代码 |

**请求示例**:
```
GET http://172.26.100.9:5005/api/specs?spec_number=11-CL-402B&alloy_grade=23Co14Ni12Cr3MoE
```

**响应示例**:
```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "spec_number": "11-CL-402B",
      "alloy_grade": "23Co14Ni12Cr3MoE",
      "status": "淬火+回火",
      "specification": "棒材",
      "sampling_direction": "纵向",
      "test_category": {
        "id": 2,
        "name": "拉伸",
        "code": "tension"
      },
      "test_values": {
        "tensile_strength": {
          "min_value": "1930",
          "comparison": "≥",
          "unit": "MPa",
          "item_key": ["抗拉"],
          "experimental_conditions": {"temperature": "室温"}
        },
        "yield_strength": {
          "min_value": "1620",
          "comparison": "≥",
          "unit": "MPa",
          "item_key": ["屈服"],
          "experimental_conditions": {"temperature": "室温"}
        }
      },
      "additional_conditions": {
        "heat_treatment": "淬火: 885±15℃, 保温 60±5 min, 油冷"
      },
      "remarks": "",
      "created_at": "2026-06-05 19:56:34"
    }
  ]
}
```

---

### 6. 查询材料规范数据 (POST)

**接口地址**: `POST /api/query`

**说明**: 使用 POST 方式查询材料规范数据，支持 JSON 请求体

**请求头**:
```
Content-Type: application/json
```

**请求体**:

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| material_spec_number | string | 否 | 标准号/编号，精确匹配 |
| alloy_grade | string | 否 | 牌号，模糊匹配 |
| status | string | 否 | 状态，模糊匹配 |
| specification | string | 否 | 规格，精确匹配 |
| sampling_direction | string | 否 | 取样方向，精确匹配 |
| test_category_code | string | 否 | 测试类别代码 |
| update_time | string | 否 | 更新时间筛选，查询此时间之后更新的记录，格式：YYYY-MM-DD 或 YYYY-MM-DD HH:MM:SS |

**请求体示例**:
```json
{
  "material_spec_number": "11-CL-402B",
  "alloy_grade": "23Co14Ni12Cr3MoE",
  "status": "",
  "specification": "",
  "sampling_direction": "纵向",
  "test_category_code": "tension",
  "update_time": ""
}
```

**请求示例**:
```bash
curl -X POST "http://172.26.100.9:5005/api/query" \
  -H "Content-Type: application/json" \
  -d '{
    "material_spec_number": "11-CL-402B",
    "alloy_grade": "23Co14Ni12Cr3MoE",
    "status": "",
    "specification": "",
    "sampling_direction": "纵向",
    "test_category_code": "tension",
    "update_time": ""
  }'
```

**响应示例**:
```json
{
  "success": true,
  "query": {
    "material_spec_number": "11-CL-402B",
    "alloy_grade": "23Co14Ni12Cr3MoE",
    "status": "",
    "specification": "",
    "sampling_direction": "纵向",
    "test_category_code": "tension",
    "update_time": ""
  },
  "data": [
    {
      "id": 1,
      "spec_number": "11-CL-402B",
      "alloy_grade": "23Co14Ni12Cr3MoE",
      "status": "淬火: 885±15℃, 保温 60±5 min, 油冷; 冷处理: -73±8℃, 保温 60±5 min, 空气中回温; 回火: 482±3℃, 保温 5~8h, 空冷",
      "specification": "直径小于等于 300mm 的棒材锻制的锻件",
      "sampling_direction": "纵向",
      "test_category": {
        "id": 2,
        "name": "拉伸",
        "code": "tension"
      },
      "test_values": {
        "tensile_strength": {
          "min_value": "1930",
          "max_value": null,
          "comparison": "≥",
          "unit": "MPa",
          "field_name": "抗拉强度 R<sub>m</sub>",
          "item_key": ["抗拉"],
          "experimental_conditions": {"temperature": "室温"}
        },
        "yield_strength": {
          "min_value": "1620",
          "max_value": null,
          "comparison": "≥",
          "unit": "MPa",
          "field_name": "屈服强度 R<sub>p0.2</sub>",
          "item_key": ["屈服"],
          "experimental_conditions": {"temperature": "室温"}
        },
        "elongation_5d": {
          "min_value": "10",
          "max_value": null,
          "comparison": "≥",
          "unit": "%",
          "field_name": "断后伸长率 A<sub>5D</sub>",
          "item_key": ["伸长"],
          "experimental_conditions": {"temperature": "室温"}
        },
        "elongation_4d": {
          "min_value": null,
          "max_value": null,
          "comparison": "≥",
          "unit": "%",
          "field_name": "断后伸长率 A<sub>4D</sub>",
          "item_key": ["伸长"],
          "experimental_conditions": {"temperature": "室温"}
        },
        "reduction_of_area": {
          "min_value": "55",
          "max_value": null,
          "comparison": "",
          "unit": "%",
          "field_name": "断面收缩率 Z",
          "item_key": ["收缩"],
          "experimental_conditions": {"temperature": "室温"}
        }
      },
      "additional_conditions": {},
      "remarks": null,
      "created_at": "2026-06-05 19:56:34"
    }
  ]
}
```

---

### 7. 获取统计数据

**接口地址**: `GET /api/statistics`

**说明**: 获取数据库统计信息

**响应示例**:
```json
{
  "success": true,
  "data": {
    "total_specs": 10,
    "total_categories": 5,
    "total_alloy_grades": 8,
    "total_spec_numbers": 10
  }
}
```

---

## 测试类别代码参考

| 代码 | 名称 |
|------|------|
| chemical_composition | 化学成分 |
| tension | 拉伸 |
| impact | 冲击 |
| hardness | 硬度 |
| bending | 弯曲 |

---

## 错误响应

当请求失败时，API 返回以下格式的错误信息：

```json
{
  "success": false,
  "error": "错误描述信息"
}
```

**常见错误代码**:
- `400`: 请求参数错误
- `404`: 资源不存在
- `500`: 服务器内部错误
