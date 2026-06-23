# 材料规范数据库 - 数据结构说明

## 概述

本文档详细说明材料规范数据库的数据结构，包括所有表结构、字段定义及含义。

---

## 1. 数据库表结构

### 1.1 MaterialSpec（材料规范主表）

| 字段名 | 数据类型 | 必填 | 说明 |
|--------|----------|------|------|
| `id` | Integer | 是 | 主键ID，自增 |
| `material_spec_number` | String(100) | 是 | **编号**，材料规范的唯一标识符，如"GJB 1234-2023" |
| `test_category_id` | Integer | 是 | 外键，关联测试类别表(TestCategory) |
| `alloy_grade` | String(100) | 是 | **牌号**，材料的具体牌号，如"30Si2MnCrMoVE" |
| `status` | String(100) | 是 | **状态**，材料的热处理状态，如"正火+淬火+回火" |
| `specification` | String(200) | 是 | **规格**，材料的规格，如"棒材"、"板材"、"锻件" |
| `sampling_direction` | String(50) | 是 | **取样方向**，如"纵向"、"横向"、"高向" |
| `additional_conditions` | Text | 否 | **附加条件**，JSON格式存储热处理工艺等信息 |
| `remarks` | Text | 否 | **备注**，其他说明信息 |
| `created_at` | DateTime | 是 | 创建时间 |
| `updated_at` | DateTime | 是 | 更新时间 |

---

### 1.2 TestValue（性能指标表）

| 字段名 | 数据类型 | 说明 |
|--------|----------|------|
| `id` | Integer | 主键ID |
| `spec_id` | Integer | 外键，关联材料规范表(MaterialSpec) |
| `field_definition_id` | Integer | 外键，关联字段定义表(TestFieldDefinition) |
| `item_key` | Text (JSON数组) | **项目关键字（多值）**，JSON数组格式，用于查询匹配。查询时只要与数组中任一值匹配即可。<br>示例：`["高温", "抗拉"]`<br>**自动生成规则**：导入或录入时如果用户未填写，系统将自动从 `field_name` 中提取1-2个关键字。详见第10章 |
| `experimental_conditions` | JSON | **试验条件**，JSON格式存储该测试的环境参数，见试验条件约束表 |
| `string_value` | Text | 字符串类型的值（如试验温度"室温"） |
| `number_value` | String(50) | 数值类型的值（保留原始精度） |
| `min_value` | String(50) | 最小值（范围类型，保留原始精度） |
| `max_value` | String(50) | 最大值（范围类型，保留原始精度） |
| `comparison` | String(20) | **比较符号**，如"≥"、"≤"、"="、"＞"、"＜" |
| `unit` | String(50) | **单位**，如"MPa"、"%"、"℃"、"HV" |
| `created_at` | DateTime | 创建时间 |
| `updated_at` | DateTime | 更新时间 |

**experimental_conditions JSON结构：**
```json
{
  "temperature": null,
  "stress": null,
  "test_time": null,
  "strain": null,
  "speed": null,
  "other_conditions": null
}
```

---

### 1.3 TestCategory（测试类别表）

| 字段名 | 数据类型 | 说明 |
|--------|----------|------|
| `id` | Integer | 主键ID |
| `name` | String(100) | 类别名称，如"拉伸"、"冲击" |
| `code` | String(50) | 类别代码，如"tension"、"impact" |
| `description` | Text | 描述 |
| `is_active` | Boolean | 是否启用 |
| `sort_order` | Integer | 排序顺序 |

---

### 1.4 ExperimentalConditionField（试验条件字段定义表）

| 字段名 | 数据类型 | 说明 |
|--------|----------|------|
| `id` | Integer | 主键ID |
| `field_code` | String(50) | 字段代码，如"temperature" |
| `field_name` | String(100) | 字段名称，如"温度" |
| `field_type` | String(20) | 字段类型：number(数字)、text(文本) |
| `unit` | String(50) | 单位，如"℃"、"MPa"、"h" |
| `description` | Text | 描述 |
| `sort_order` | Integer | 排序顺序 |

---

### 1.5 ConditionConstraint（试验条件约束表）

| 字段名 | 数据类型 | 说明 |
|--------|----------|------|
| `id` | Integer | 主键ID |
| `category_id` | Integer | 外键，关联测试类别表(TestCategory) |
| `field_code` | String(50) | 试验条件字段代码 |
| `is_required` | Boolean | 是否必填 |
| `is_allowed` | Boolean | 是否允许填写（用于排除不需要的字段） |
| `mutually_exclusive_group` | String(50) | 互斥字段组名称（如"stress_strain"，同组内字段只能填写其中一个） |

**约束规则说明：**
- `other_conditions` 字段对所有类别均允许填写但不强制
- 当 `is_allowed=false` 时，该字段在对应类别下不可编辑
- 当 `is_allowed=true` 且 `is_required=true` 时，该字段必须填写
- 当 `is_allowed=true` 且 `is_required=false` 时，该字段可选填写
- **互斥字段**：当 `is_mutually_exclusive=true` 时，同一组内的字段只能填写其中一个

**各测试类别的试验条件约束配置：**

| 测试类别 | 允许字段 | 必填字段 | 互斥字段组 |
|----------|----------|----------|------------|
| chemical_composition | other_conditions | - | - |
| tension | temperature, other_conditions | temperature | - |
| impact | temperature, other_conditions | temperature | - |
| stress_rupture | temperature, stress, test_time, other_conditions | temperature, stress, test_time | - |
| creep | temperature, stress, test_time, other_conditions | temperature, stress, test_time | - |
| hardness | other_conditions | - | - |
| fracture_toughness | temperature, other_conditions | temperature | - |
| macro_structure | other_conditions | - | - |
| fracture_inspection | other_conditions | - | - |
| grain_size | other_conditions | - | - |
| non_metallic_inclusion | other_conditions | - | - |
| microstructure | other_conditions | - | - |
| high_cycle_fatigue | temperature, stress, strain, other_conditions | temperature | stress,strain |
| low_cycle_fatigue | temperature, stress, strain, other_conditions | temperature | stress,strain |
| rotary_bending_fatigue | temperature, stress, speed, other_conditions | temperature, stress, speed | - |

---

### 1.6 TestFieldDefinition（字段定义表）

| 字段名 | 数据类型 | 说明 |
|--------|----------|------|
| `id` | Integer | 主键ID |
| `category_id` | Integer | 外键，关联测试类别(TestCategory) |
| `field_name` | String(100) | 字段显示名称，如"抗拉强度" |
| `field_code` | String(50) | 字段代码，如"tensile_strength" |
| `field_type` | String(20) | 字段类型：range(范围)、string(字符串)、number(数字)、text(文本) |
| `unit` | String(50) | 默认单位 |
| `is_required` | Boolean | 是否必填 |
| `sort_order` | Integer | 排序顺序 |

---

### 1.7 FieldMapping（字段映射表）

| 字段名 | 数据类型 | 说明 |
|--------|----------|------|
| `id` | Integer | 主键ID |
| `source_field` | String(100) | 源字段名（大模型识别可能出错的字段名） |
| `target_field_code` | String(50) | 目标字段代码（数据库中正确的字段代码） |
| `category_code` | String(50) | 适用的类别代码（空表示通用） |
| `is_active` | Boolean | 是否启用 |
| `created_at` | DateTime | 创建时间 |

---

## 2. 测试类别及字段定义

### 2.1 化学成分 (chemical_composition)

| 字段代码 | 字段名称 | 字段类型 | 单位 |
|----------|----------|----------|------|
| c | 碳 C | range | % |
| cr | 铬 Cr | range | % |
| mo | 钼 Mo | range | % |
| al | 铝 Al | range | % |
| ti | 钛 Ti | range | % |
| co | 钴 Co | range | % |
| b | 硼 B | range | % |
| ni | 镍 Ni | range | % |
| si | 硅 Si | range | % |
| mn | 锰 Mn | range | % |
| s | 硫 S | range | % |
| p | 磷 P | range | % |
| zr | 锆 Zr | range | % |
| cu | 铜 Cu | range | % |
| fe | 铁 Fe | range | % |
| pb | 铅 Pb | range | % |
| as | 砷 As | range | % |
| sn | 锡 Sn | range | % |
| sb | 锑 Sb | range | % |
| bi | 铋 Bi | range | % |
| ag | 银 Ag | range | % |
| nb | 铌 Nb | range | % |
| mg | 镁 Mg | range | % |

### 2.2 拉伸 (tension)

| 字段代码 | 字段名称 | 字段类型 | 单位 |
|----------|----------|----------|------|
| tensile_strength | 抗拉强度 R<sub>m</sub> | range | MPa |
| yield_strength | 屈服强度 R<sub>p0.2</sub> | range | MPa |
| proof_strength | 规定塑性延伸强度 R<sub>p0.2</sub> | range | MPa |
| upper_yield_strength | 上屈服强度 R<sub>eH</sub> | range | MPa |
| lower_yield_strength | 下屈服强度 R<sub>eL</sub> | range | MPa |
| reduction_of_area | 断面收缩率 Z | range | % |
| elongation_5d | 断后伸长率 A<sub>5D</sub> | range | % |
| elongation_4d | 断后伸长率 A<sub>4D</sub> | range | % |

### 2.3 冲击 (impact)

| 字段代码 | 字段名称 | 字段类型 | 单位 |
|----------|----------|----------|------|
| impact_energy | 冲击吸收能量 | range | J |
| impact_energy_ku2 | 冲击吸收能量A<sub>Ku2</sub> | range | J |
| impact_energy_kv2 | 冲击吸收能量A<sub>Kv2</sub> | range | J |
| a_ku2 | A_Ku2 | range | J |

### 2.4 持久 (stress_rupture)

| 字段代码 | 字段名称 | 字段类型 | 单位 |
|----------|----------|----------|------|
| stress | 应力σ | range | MPa |
| rupture_time | 持久时间 | range | h |
| creep_reduction_of_area | 蠕变断面收缩率Z<sub>u</sub> | range | % |
| creep_elongation_4d | 蠕变断后伸长率δ₄ | range | % |
| creep_elongation_5d | 蠕变断后伸长率δ₅ | range | % |

### 2.5 蠕变 (creep)

| 字段代码 | 字段名称 | 字段类型 | 单位 |
|----------|----------|----------|------|
| stress | 应力 | number | MPa |
| creep_reduction_of_area | 蠕变断面收缩率Z<sub>u</sub> | range | % |
| creep_elongation_4d | 蠕变断后伸长率A<sub>4d</sub> | range | % |
| creep_elongation_5d | 蠕变断后伸长率A<sub>5d</sub> | range | % |

### 2.6 硬度 (hardness)

| 字段代码 | 字段名称 | 字段类型 | 单位 |
|----------|----------|----------|------|
| hardness_type | 硬度类型 | string | - |
| scale | 标尺 | string | - |
| hardness_value | 硬度值 | range | - |

### 2.7 断裂韧度 (fracture_toughness)

| 字段代码 | 字段名称 | 字段类型 | 单位 |
|----------|----------|----------|------|
| fracture_toughness | 断裂韧度K<sub>ⅠC</sub> | range | MPam<sup>-1/2</sup> |

### 2.8 宏观组织 (macro_structure)

| 字段代码 | 字段名称 | 字段类型 |
|----------|----------|----------|
| macro_structure | 宏观组织 | text |

### 2.9 断口检验 (fracture_inspection)

| 字段代码 | 字段名称 | 字段类型 |
|----------|----------|----------|
| fracture_inspection_description | 要求描述 | text |

### 2.10 晶粒度 (grain_size)

| 字段代码 | 字段名称 | 字段类型 |
|----------|----------|----------|
| grain_size_description | 要求描述 | text |

### 2.11 非金属夹杂 (non_metallic_inclusion)

| 字段代码 | 字段名称 | 字段类型 |
|----------|----------|----------|
| non_metallic_inclusion_description | 要求描述 | text |

### 2.12 显微组织 (microstructure)

| 字段代码 | 字段名称 | 字段类型 |
|----------|----------|----------|
| microstructure_description | 要求描述 | text |

### 2.13 高周疲劳 (high_cycle_fatigue)

| 字段代码 | 字段名称 | 字段类型 | 单位 |
|----------|----------|----------|------|
| number_of_cycles | 循环次数 | number | 次 |

### 2.14 低周疲劳 (low_cycle_fatigue)

| 字段代码 | 字段名称 | 字段类型 | 单位 |
|----------|----------|----------|------|
| number_of_cycles | 循环次数 | number | 次 |

### 2.15 旋转弯曲疲劳 (rotary_bending_fatigue)

| 字段代码 | 字段名称 | 字段类型 | 单位 |
|----------|----------|----------|------|
| number_of_cycles | 循环次数 | number | 次 |

---

## 3. 数据格式说明

### 3.1 范围类型 (range)

用于表示数值范围，格式如下：

```json
{
    "min_value": "0.70",
    "max_value": "1.00",
    "comparison": "≥",
    "unit": "%"
}
```

### 3.2 数值类型 (number)

用于表示单个数值，格式如下：

```json
{
    "value": "1620",
    "unit": "MPa"
}
```

### 3.3 字符串类型 (string)

用于表示字符串值，格式如下：

```json
{
    "value": "室温"
}
```

### 3.4 文本类型 (text)

用于表示长文本描述，格式如下：

```json
{
    "value": "要求描述内容"
}
```

---

## 4. 附加条件 (additional_conditions)

`additional_conditions` 字段以 JSON 格式存储附加条件，示例：

```json
{
    "heat_treatment": "淬火+回火",
    "sample_size": "φ10mm",
    "test_standard": "GB/T 228.1-2010"
}
```

---

## 5. 字段映射说明

字段映射用于将大模型识别出的字段名转换为数据库中的标准字段代码。

### 5.1 映射规则

- **源字段名**：大模型可能识别错误的字段名（如 δ4、delta_4、σ_b 等）
- **目标字段代码**：数据库中标准的字段代码（如 elongation_4d、tensile_strength 等）
- **类别代码**：映射适用的测试类别（空表示通用）

### 5.2 映射示例

| 目标字段代码 | 源字段名（示例） |
|------------|-----------------|
| elongation_5d | delta_5, δ5, δ_5, 伸长率, A5D, A5, elongation_5d |
| elongation_4d | delta_4, δ4, δ_4, A4D, A4, elongation_4d |
| tensile_strength | sigma_b, σ_b, 抗拉强度, tensile_strength |
| yield_strength | sigma_0.2, σ0.2, 屈服强度, Rp0.2, yield_strength |
| reduction_of_area | psi, ψ, 断面收缩率, Z, reduction_of_area |
| stress | sigma, σ, stress, 应力 |
| rupture_time | time, t, duration, rupture_time |

---

## 6. 字段类型说明

### 6.1 range（范围类型）

适用于有数值范围的性能指标，如抗拉强度、屈服强度、伸长率等。

**存储字段**：
- `min_value`：最小值
- `max_value`：最大值
- `comparison`：比较符号（≥、≤、=、＞、＜）
- `unit`：单位

### 6.2 number（数值类型）

适用于单个数值，如温度、应力等。

**存储字段**：
- `value`：数值
- `unit`：单位

### 6.3 string（字符串类型）

适用于固定的字符串值，如硬度类型、标尺等。

**存储字段**：
- `value`：字符串值

### 6.4 text（文本类型）

适用于长文本描述，如要求描述、备注等。

**存储字段**：
- `value`：文本内容

---

## 7. API 接口说明

### 7.1 API 端点总览

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/categories` | 获取测试类别列表 |
| GET | `/api/category/<code>` | 按代码获取类别详情 |
| GET | `/api/specs` | 查询材料规范列表（支持过滤参数） |
| POST | `/api/specs` | 创建单条材料规范 |
| GET | `/api/specs/<id>` | 获取单条材料规范详情 |
| PUT | `/api/specs/<id>` | 更新材料规范 |
| DELETE | `/api/specs/<id>` | 删除材料规范 |
| POST | `/api/query` | POST方式查询材料规范 |
| GET | `/api/statistics` | 获取统计信息 |
| GET | `/api/alloy-grades` | 获取所有合金牌号列表 |
| GET | `/api/spec-numbers` | 获取所有规范编号列表 |
| POST | `/api/parse-image` | 解析上传的图片文件 |
| POST | `/api/parse-image-base64` | 解析Base64编码的图片 |
| POST | `/api/batch-import` | 批量导入材料规范 |
| GET | `/api/admin/categories` | 获取所有测试类别（含字段定义） |
| POST | `/api/admin/categories` | 创建新的测试类别 |
| PUT | `/api/admin/categories/<id>` | 更新测试类别及其字段 |
| DELETE | `/api/admin/categories/<id>` | 删除测试类别 |
| POST | `/api/admin/fields` | 添加字段定义 |
| PUT | `/api/admin/fields/<id>` | 更新字段定义 |
| DELETE | `/api/admin/fields/<id>` | 删除字段定义 |
| GET | `/api/admin/field-mappings` | 获取字段映射列表 |
| POST | `/api/admin/field-mappings` | 添加字段映射 |
| PUT | `/api/admin/field-mappings/<id>` | 更新字段映射 |
| DELETE | `/api/admin/field-mappings/<id>` | 删除字段映射 |

### 7.2 GET 查询材料规范列表

```json
GET /api/specs?material_spec_number=GJB&alloy_grade=30Si2MnCrMoVE&specification=棒材&status=正火&test_category_code=tension

响应：
{
  "success": true,
  "data": [
    {
      "id": 1,
      "material_spec_number": "GJB 1234-2023",
      "test_category": {
        "id": 1,
        "name": "拉伸",
        "code": "tension"
      },
      "alloy_grade": "30Si2MnCrMoVE",
      "status": "正火+淬火+回火",
      "specification": "棒材",
      "sampling_direction": "纵向",
      "additional_conditions": {},
      "remarks": "",
      "created_at": "2024-01-15T10:30:00",
      "updated_at": "2024-01-15T10:30:00"
    }
  ]
}
```

**支持的过滤参数：**
- `material_spec_number`：材料规范编号（模糊匹配）
- `specification`：规格
- `alloy_grade`：合金牌号
- `status`：状态
- `sampling_direction`：取样方向
- `test_category_code`：测试类别代码

### 7.3 POST 查询材料规范（支持复杂查询）

```json
POST /api/query

{
  "material_spec_number": "GJB",
  "alloy_grade": "30Si2MnCrMoVE",
  "test_category_code": "tension",
  "update_time": "2024-01"
}

响应：
{
  "success": true,
  "query": {...},
  "data": [...]
}
```

### 7.4 POST 创建材料规范（单条）

```json
POST /api/specs

{
  "material_spec_number": "GJB 1234-2023",
  "test_category_code": "tension",
  "alloy_grade": "30Si2MnCrMoVE",
  "status": "正火+淬火+回火",
  "specification": "棒材",
  "sampling_direction": "纵向",
  "additional_conditions": {
    "heat_treatment": "淬火+回火",
    "sample_size": "φ10mm",
    "test_standard": "GB/T 228.1-2010"
  },
  "remarks": "备注信息",
  "test_values": [
    {
      "field_code": "tensile_strength",
      "item_key": ["高温", "抗拉"],
      "experimental_conditions": {
        "temperature": "750℃"
      },
      "min_value": "1620",
      "max_value": "1780",
      "comparison": "≥",
      "unit": "MPa"
    },
    {
      "field_code": "yield_strength",
      "item_key": ["高温", "屈服"],
      "experimental_conditions": {
        "temperature": "750℃"
      },
      "min_value": "1420",
      "comparison": "≥",
      "unit": "MPa"
    },
    {
      "field_code": "elongation_4d",
      "item_key": ["高温", "伸长"],
      "experimental_conditions": {
        "temperature": "750℃"
      },
      "min_value": "3",
      "comparison": "≥",
      "unit": "%"
    }
  ]
}

响应：
{
  "success": true,
  "id": 1
}
```

### 7.5 GET 查询单条材料规范详情

```json
GET /api/specs/1

响应：
{
  "success": true,
  "data": {
    "id": 1,
    "material_spec_number": "GJB 1234-2023",
    "test_category": {
      "id": 1,
      "name": "拉伸",
      "code": "tension"
    },
    "alloy_grade": "30Si2MnCrMoVE",
    "status": "正火+淬火+回火",
    "specification": "棒材",
    "sampling_direction": "纵向",
    "additional_conditions": {},
    "remarks": "",
    "created_at": "2024-01-15T10:30:00",
    "updated_at": "2024-01-15T10:30:00",
    "test_values": [
      {
        "id": 1,
        "field_definition": {
          "field_code": "tensile_strength",
          "field_name": "抗拉强度 Rm",
          "field_type": "range",
          "unit": "MPa"
        },
        "item_key": ["高温", "抗拉"],
        "experimental_conditions": {
          "temperature": "750℃"
        },
        "min_value": "1620",
        "max_value": "1780",
        "comparison": "≥",
        "unit": "MPa"
      },
      {
        "id": 2,
        "field_definition": {
          "field_code": "yield_strength",
          "field_name": "屈服强度 Rp0.2",
          "field_type": "range",
          "unit": "MPa"
        },
        "item_key": ["高温", "屈服"],
        "experimental_conditions": {
          "temperature": "750℃"
        },
        "min_value": "1420",
        "comparison": "≥",
        "unit": "MPa"
      }
    ]
  }
}
```

### 7.6 PUT 更新材料规范

```json
PUT /api/specs/1

{
  "material_spec_number": "GJB 1234-2023",
  "test_category_code": "tension",
  "alloy_grade": "30Si2MnCrMoVE",
  "status": "正火+淬火+回火",
  "specification": "棒材",
  "sampling_direction": "纵向",
  "additional_conditions": {},
  "remarks": "更新后的备注",
  "test_values": [
    {
      "id": 1,
      "field_code": "tensile_strength",
      "item_key": ["高温", "抗拉"],
      "experimental_conditions": {
        "temperature": "750℃"
      },
      "min_value": "1650",
      "max_value": "1800",
      "comparison": "≥",
      "unit": "MPa"
    }
  ]
}

响应：
{
  "success": true
}
```

### 7.7 DELETE 删除材料规范

```json
DELETE /api/specs/1

响应：
{
  "success": true
}
```

### 7.8 POST 批量导入材料规范

```json
POST /api/batch-import

{
  "specs": [
    {
      "material_spec_number": "GJB 1234-2023",
      "test_category_code": "tension",
      "alloy_grade": "30Si2MnCrMoVE",
      "status": "正火+淬火+回火",
      "specification": "棒材",
      "sampling_direction": "纵向",
      "additional_conditions": {},
      "remarks": "",
      "test_values": [
        {
          "field_code": "tensile_strength",
          "item_key": ["室温", "抗拉"],
          "experimental_conditions": {
            "temperature": "室温"
          },
          "min_value": "1620",
          "comparison": "≥",
          "unit": "MPa"
        }
      ]
    },
    {
      "material_spec_number": "GJB 1234-2023",
      "test_category_code": "impact",
      "alloy_grade": "30Si2MnCrMoVE",
      "status": "正火+淬火+回火",
      "specification": "棒材",
      "sampling_direction": "纵向",
      "additional_conditions": {},
      "remarks": "",
      "test_values": [
        {
          "field_code": "impact_energy_kv2",
          "item_key": ["低温", "冲击"],
          "experimental_conditions": {
            "temperature": "-40℃"
          },
          "min_value": "47",
          "comparison": "≥",
          "unit": "J"
        }
      ]
    }
  ]
}

响应：
{
  "success": true,
  "imported_count": 2,
  "skipped_count": 0,
  "duplicates": [],
  "errors": []
}
```

### 7.9 图片识别接口

```json
// 方式1：上传文件
POST /api/parse-image
Content-Type: multipart/form-data

file: <图片文件>
test_category_code: tension

响应：
{
  "success": true,
  "data": [
    {
      "field_code": "tensile_strength",
      "item_key": ["高温", "抗拉"],
      "experimental_conditions": {
        "temperature": "750℃"
      },
      "min_value": "1620",
      "max_value": "1780",
      "comparison": "≥",
      "unit": "MPa"
    }
  ]
}

// 方式2：Base64编码
POST /api/parse-image-base64
Content-Type: application/json

{
  "image_data": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAA...",
  "test_category_code": "tension"
}

响应：
{
  "success": true,
  "data": [...],
  "elapsed": 2.35
}
```

### 7.10 GET 获取测试类别列表

```json
GET /api/categories

响应：
{
  "success": true,
  "data": [
    {
      "id": 1,
      "name": "拉伸",
      "code": "tension",
      "description": "拉伸性能试验",
      "is_active": true,
      "sort_order": 1,
      "field_definitions": [
        {
          "id": 1,
          "field_name": "抗拉强度 Rm",
          "field_code": "tensile_strength",
          "field_type": "range",
          "unit": "MPa",
          "is_required": false,
          "sort_order": 0
        }
      ]
    }
  ]
}
```

### 7.11 GET 获取统计信息

```json
GET /api/statistics

响应：
{
  "success": true,
  "data": {
    "total_specs": 150,
    "total_categories": 15,
    "specs_by_category": {
      "tension": 45,
      "impact": 38,
      "chemical_composition": 30
    }
  }
}
```

### 7.12 管理接口 - 测试类别

```json
// 创建测试类别
POST /api/admin/categories
{
  "name": "新类别",
  "code": "new_category",
  "description": "类别描述",
  "fields": [
    {
      "field_name": "新字段",
      "field_code": "new_field",
      "field_type": "range",
      "unit": "MPa"
    }
  ]
}

// 更新测试类别（含字段更新）
PUT /api/admin/categories/1
{
  "name": "更新后的类别名",
  "code": "updated_code",
  "description": "更新后的描述",
  "is_active": true,
  "sort_order": 1,
  "fields": [
    {
      "field_code": "new_field",
      "field_name": "新字段",
      "field_type": "range",
      "unit": "MPa",
      "is_required": false,
      "sort_order": 0
    }
  ]
}

// 删除测试类别
DELETE /api/admin/categories/1
```

### 7.13 管理接口 - 字段映射

```json
// 获取字段映射
GET /api/admin/field-mappings?category_code=tension&active_only=true&merge_sources=true

响应：
{
  "success": true,
  "data": [
    {
      "id": 1,
      "source_fields": ["Rm", "抗拉强度Rm", "Rm MPa"],
      "target_field_code": "tensile_strength",
      "category_code": "tension",
      "is_active": true
    }
  ]
}

// 添加字段映射
POST /api/admin/field-mappings
{
  "source_fields": ["高温抗拉"],
  "target_field_code": "tensile_strength",
  "category_code": "tension"
}

// 更新字段映射
PUT /api/admin/field-mappings/1
{
  "source_fields": ["Rm", "抗拉强度"],
  "target_field_code": "tensile_strength",
  "category_code": "tension",
  "is_active": true
}

// 删除字段映射
DELETE /api/admin/field-mappings/1
```

---

## 8. 数据结构关系图

```
MaterialSpec（材料规范主表）
├── id
├── material_spec_number（编号）
├── test_category_id → TestCategory（测试类别）
├── alloy_grade（牌号）
├── status（状态）
├── specification（规格）
├── sampling_direction（取样方向）
├── additional_conditions（附加条件）
├── remarks（备注）
├── created_at
├── updated_at
│
└── test_values: []（性能指标列表）
    └── TestValue（性能指标）
        ├── id
        ├── field_definition_id → TestFieldDefinition（字段定义）
        ├── item_key（项目关键字，JSON数组，如["高温","抗拉"]）
        ├── experimental_conditions（试验条件）
        ├── string_value / number_value
        ├── min_value / max_value
        ├── comparison
        └── unit
```

---

## 9. 试验条件约束速查表

| 测试类别 | 允许填写的试验条件 | 必填条件 | 互斥字段 |
|----------|-------------------|----------|----------|
| chemical_composition | other_conditions | - | - |
| tension | temperature, other_conditions | temperature | - |
| impact | temperature, other_conditions | temperature | - |
| stress_rupture | temperature, stress, test_time, other_conditions | temperature, stress, test_time | - |
| creep | temperature, stress, test_time, other_conditions | temperature, stress, test_time | - |
| hardness | other_conditions | - | - |
| fracture_toughness | temperature, other_conditions | temperature | - |
| macro_structure | other_conditions | - | - |
| fracture_inspection | other_conditions | - | - |
| grain_size | other_conditions | - | - |
| non_metallic_inclusion | other_conditions | - | - |
| microstructure | other_conditions | - | - |
| high_cycle_fatigue | temperature, stress, strain, other_conditions | temperature | stress ↔ strain |
| low_cycle_fatigue | temperature, stress, strain, other_conditions | temperature | stress ↔ strain |
| rotary_bending_fatigue | temperature, stress, speed, other_conditions | temperature, stress, speed | - |

**说明**：
- `other_conditions` 对所有测试类别均允许填写，但不强制
- `temperature` 在 tension、impact、stress_rupture、creep、fracture_toughness、high_cycle_fatigue、low_cycle_fatigue、rotary_bending_fatigue 类别下为必填
- high_cycle_fatigue 和 low_cycle_fatigue 中 `stress` 和 `strain` 为互斥字段，只能填写其中一个

---

## 10. item_key 自动生成规则

### 10.1 数据格式

`item_key` 使用 **JSON 数组**格式存储多个关键字，支持查询时灵活匹配。

```json
// 存储示例
"item_key": ["高温", "抗拉"]

// 查询示例
// 输入 "高温" → 匹配成功 ✅
// 输入 "抗拉" → 匹配成功 ✅
// 输入 "低温" → 匹配失败 ❌
```

### 10.2 生成逻辑

在导入或录入数据时，`item_key` 按以下规则自动生成：

1. **用户优先**：如果用户已提供 `item_key`，直接使用用户输入
2. **自动提取**：如果用户未提供，从 `field_name` 中自动提取1-2个关键字

### 10.3 提取规则

系统按以下优先级提取关键字（最多2个）：

| 优先级 | 关键字类型 | 示例 | 提取结果 |
|--------|-----------|------|----------|
| 1 | 温度相关 | "高温抗拉强度 Rm" | ["高温", "抗拉"] |
| 2 | 强度相关 | "屈服强度 Rp0.2" | ["屈服"] |
| 3 | 塑性相关 | "伸长率 A5D" | ["伸长"] |
| 4 | 其他常见 | "冲击吸收能量" | ["冲击"] |

### 10.4 提取示例

| field_name | 提取逻辑 | item_key (JSON数组) |
|------------|---------|-------------------|
| "高温抗拉强度 Rm" | 温度+强度 | ["高温", "抗拉"] |
| "低温冲击吸收能量 AKu2" | 温度+冲击 | ["低温", "冲击"] |
| "抗拉强度 Rm" | 强度 | ["抗拉"] |
| "伸长率 A5D" | 塑性 | ["伸长"] |
| "室温屈服强度 Rp0.2" | 温度+屈服 | ["室温", "屈服"] |
| "蠕变断面收缩率" | 蠕变 | ["蠕变"] |
| "硬度值" | 无匹配 | [] (空数组) |

### 10.5 用户输入格式支持

系统支持多种用户输入格式：

```json
// 字符串（自动转为单元素数组）
"高温" → ["高温"]

// 逗号分隔字符串（自动拆分为数组）
"高温,抗拉" → ["高温", "抗拉"]

// 直接传入数组
["高温", "抗拉"] → ["高温", "抗拉"]
```

### 10.6 查询匹配

使用 `match_item_key()` 函数进行匹配：

```python
from database.models import match_item_key

# 数据库记录
record_item_key = '["高温", "抗拉"]'

# 查询匹配 - 与数组中任一元素匹配即可
match_item_key(record_item_key, "高温")  # 返回 True
match_item_key(record_item_key, "抗拉")  # 返回 True
match_item_key(record_item_key, "低温")  # 返回 False
```

### 10.7 代码示例

```python
from database.models import generate_item_key

# 用户已填写，直接返回 JSON 数组
generate_item_key("高温抗拉强度 Rm", "高温")
# 结果：'["高温"]'

# 用户输入逗号分隔的多关键字
generate_item_key("高温抗拉强度 Rm", "高温,抗拉")
# 结果：'["高温", "抗拉"]'

# 用户未填写，自动提取
generate_item_key("高温抗拉强度 Rm", None)
# 结果：'["高温", "抗拉"]'

# 用户未填写且无匹配关键字
generate_item_key("其他字段", None)
# 结果：'[]'
```
