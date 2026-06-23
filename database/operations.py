from sqlalchemy.orm import sessionmaker
from .models import (
    MaterialSpec, TestValue, TestCategory, TestFieldDefinition,
    init_db, init_default_categories, FieldMapping, generate_item_key
)
import json
import re


# 化学元素代码到名称的映射
ELEMENT_NAMES = {
    'c': '碳', 'C': 'C',
    'cr': '铬', 'Cr': 'Cr',
    'mo': '钼', 'Mo': 'Mo',
    'al': '铝', 'Al': 'Al',
    'ti': '钛', 'Ti': 'Ti',
    'co': '钴', 'Co': 'Co',
    'b': '硼', 'B': 'B',
    'ni': '镍', 'Ni': 'Ni',
    'si': '硅', 'Si': 'Si',
    'mn': '锰', 'Mn': 'Mn',
    's': '硫', 'S': 'S',
    'p': '磷', 'P': 'P',
    'zr': '锆', 'Zr': 'Zr',
    'cu': '铜', 'Cu': 'Cu',
    'fe': '铁', 'Fe': 'Fe',
    'pb': '铅', 'Pb': 'Pb',
    'as': '砷', 'As': 'As',
    'sn': '锡', 'Sn': 'Sn',
    'sb': '锑', 'Sb': 'Sb',
    'bi': '铋', 'Bi': 'Bi',
    'ag': '银', 'Ag': 'Ag',
    'v': '钒', 'V': 'V',
    'w': '钨', 'W': 'W',
    'nb': '铌', 'Nb': 'Nb',
    'ta': '钽', 'Ta': 'Ta',
    'mg': '镁', 'Mg': 'Mg',
}


def _generate_chemical_item_key(field_code: str) -> str:
    """
    为化学成分字段生成 item_key
    
    Args:
        field_code: 字段代码，如 'c', 'co', 'ni'
    
    Returns:
        JSON 数组格式的 item_key，如 '["C"]' 或 '["碳"]'
    """
    # 优先使用大写字母格式
    upper_code = field_code.upper()
    if upper_code in ELEMENT_NAMES:
        return json.dumps([upper_code], ensure_ascii=False)
    # 如果找不到，尝试小写
    lower_code = field_code.lower()
    if lower_code in ELEMENT_NAMES:
        return json.dumps([lower_code.upper()], ensure_ascii=False)
    # 如果都找不到，返回字段代码本身
    return json.dumps([field_code], ensure_ascii=False)

def _init_default_field_mappings(session):
    default_mappings = [
        {"source_field": "HRC", "target_field_code": "hardness_value", "category_code": "hardness"},
        {"source_field": "HB", "target_field_code": "hardness_value", "category_code": "hardness"},
        {"source_field": "HBW", "target_field_code": "hardness_value", "category_code": "hardness"},
        {"source_field": "HV", "target_field_code": "hardness_value", "category_code": "hardness"},
        {"source_field": "HRA", "target_field_code": "hardness_value", "category_code": "hardness"},
        {"source_field": "HRB", "target_field_code": "hardness_value", "category_code": "hardness"},
        {"source_field": "HRD", "target_field_code": "hardness_value", "category_code": "hardness"},
        {"source_field": "HRE", "target_field_code": "hardness_value", "category_code": "hardness"},
        {"source_field": "HRF", "target_field_code": "hardness_value", "category_code": "hardness"},
        {"source_field": "HRG", "target_field_code": "hardness_value", "category_code": "hardness"},
        {"source_field": "HRP", "target_field_code": "hardness_value", "category_code": "hardness"},
        {"source_field": "HRS", "target_field_code": "hardness_value", "category_code": "hardness"},
        {"source_field": "HRV", "target_field_code": "hardness_value", "category_code": "hardness"},
        {"source_field": "HV10", "target_field_code": "hardness_value", "category_code": "hardness"},
        {"source_field": "HV30", "target_field_code": "hardness_value", "category_code": "hardness"},
        {"source_field": "K_IC", "target_field_code": "fracture_toughness", "category_code": "fracture_toughness"},
        {"source_field": "K_Ic", "target_field_code": "fracture_toughness", "category_code": "fracture_toughness"},
        {"source_field": "k_ic", "target_field_code": "fracture_toughness", "category_code": "fracture_toughness"},
        {"source_field": "KIC", "target_field_code": "fracture_toughness", "category_code": "fracture_toughness"},
        {"source_field": "K1C", "target_field_code": "fracture_toughness", "category_code": "fracture_toughness"},
    ]
    
    for mapping_data in default_mappings:
        existing = session.query(FieldMapping).filter_by(
            source_field=mapping_data["source_field"],
            target_field_code=mapping_data["target_field_code"],
            category_code=mapping_data["category_code"]
        ).first()
        
        if not existing:
            mapping = FieldMapping(
                source_field=mapping_data["source_field"],
                target_field_code=mapping_data["target_field_code"],
                category_code=mapping_data["category_code"],
                is_active=True
            )
            session.add(mapping)
    
    session.commit()


def _format_number(value):
    """返回原始字符串值，确保数字精度不丢失"""
    if value is None:
        return None
    # 直接返回字符串值，不做任何格式化
    return str(value) if not isinstance(value, str) else value


def _normalize_unit(unit, category_code):
    """规范化单位显示格式"""
    if not unit or not category_code:
        return unit

    if category_code == 'fracture_toughness':
        unit = unit.replace('MPa√m', 'MPa·m⁻¹/²')
        unit = unit.replace('MPa·√m', 'MPa·m⁻¹/²')

    return unit


def _normalize_comparison(comparison):
    """规范化比较符号：将 >=、<= 等替换为 ≥、≤

    支持的写法：
      >=  =>  →  ≥
      <=  =<  →  ≤
      HTML 实体 &gt;= &lt;= &ge; &le;
      全角 ＞ ＜ ＞= ＜=
    """
    if comparison is None:
        return comparison
    comparison = str(comparison)
    if not comparison:
        return comparison

    replacements = [
        ('&gt;=', '≥'), ('&lt;=', '≤'),
        ('&ge;', '≥'), ('&le;', '≤'),
        ('＞=', '≥'), ('＜=', '≤'),
        ('＞', '≥'), ('＜', '≤'),
        ('>=', '≥'), ('=>', '≥'),
        ('<=', '≤'), ('=<', '≤'),
    ]
    for old, new in replacements:
        comparison = comparison.replace(old, new)
    return comparison


# 需要温度字段的测试类别（未填写时默认"室温"）
_TEMPERATURE_REQUIRED_CATEGORIES = {
    'tension', 'impact', 'stress_rupture', 'creep',
    'fracture_toughness', 'high_cycle_fatigue', 'low_cycle_fatigue',
    'rotary_bending_fatigue',
}


# 类别代码别名：把 LLM 输出的常见拼写错误映射到数据库中的正确代码
_CATEGORY_CODE_ALIASES = {
    'non_metallic_inclusions': 'non_metallic_inclusion',
}


def _normalize_category_code(category_code):
    """规范化测试类别代码

    将 LLM 输出的常见拼写变体映射到数据库定义的标准代码。
    """
    if not category_code:
        return category_code
    return _CATEGORY_CODE_ALIASES.get(category_code, category_code)


# 含 description/text 字段的类别：超出字段值时聚合到该字段
_TEXT_AGGREGATION_TARGETS = {
    'non_metallic_inclusion': 'non_metallic_inclusion_description',
    'macro_structure': 'macro_structure_description',
    'grain_size': 'grain_size_description',
    'microstructure': 'microstructure_description',
    'fracture_inspection': 'fracture_inspection_description',
}


def _aggregate_orphan_fields(spec_data, field_map):
    """将 test_values 中未匹配的字段聚合到该类别的 text 字段

    场景：LLM 输出多个细分字段（如 inclusion_type_A_coarse、A_fine 等），
    但数据库只定义了 requirement_description 一个 text 字段。
    将这些 orphan 字段的键值拼接成描述文本，合并到目标 text 字段。

    返回：是否发生了聚合（True/False）
    """
    if not isinstance(spec_data, dict):
        return False

    category_code = spec_data.get('test_category_code', '')
    target_field = _TEXT_AGGREGATION_TARGETS.get(category_code)
    if not target_field:
        return False

    test_values = spec_data.get('test_values')
    if not isinstance(test_values, dict):
        return False

    orphan_lines = []
    kept = {}
    for field_code, value_data in test_values.items():
        if field_code == '_experimental_conditions_placeholder':
            kept[field_code] = value_data
            continue
        if field_code in field_map:
            kept[field_code] = value_data
            continue
        # orphan field：只拼接内容，不带 field_code 前缀和 key=value 格式
        if isinstance(value_data, dict):
            parts = []
            for k, v in value_data.items():
                if k in ('experimental_conditions', 'item_key', 'unit', 'comparison'):
                    continue
                if v in (None, '', [], {}):
                    continue
                parts.append(str(v))
            if parts:
                orphan_lines.append("".join(parts))
        elif value_data not in (None, '', []):
            orphan_lines.append(str(value_data))

    if not orphan_lines:
        return False

    # 合并到目标字段（已有内容则追加）
    target_value = kept.get(target_field, {})
    if not isinstance(target_value, dict):
        target_value = {'value': str(target_value) if target_value else ''}

    existing_text = target_value.get('value', '') or ''
    combined = (existing_text + '\n' + '\n'.join(orphan_lines)).strip() if existing_text else '\n'.join(orphan_lines).strip()
    target_value['value'] = combined
    if 'item_key' not in target_value:
        target_value['item_key'] = []
    if 'experimental_conditions' not in target_value:
        target_value['experimental_conditions'] = {}

    kept[target_field] = target_value
    spec_data['test_values'] = kept
    return True


def _normalize_experimental_conditions(exp_cond, category_code):
    """规范化试验条件

    规则：
    - 若 category_code 属于需要温度的类别，且 exp_cond 中没有 temperature
      （None 或缺失），则自动填充为 "室温"。
    - 其他情况原样返回。
    """
    if not isinstance(exp_cond, dict):
        return exp_cond
    if category_code not in _TEMPERATURE_REQUIRED_CATEGORIES:
        return exp_cond

    if not exp_cond.get('temperature'):
        exp_cond = dict(exp_cond)
        exp_cond['temperature'] = '室温'
    return exp_cond

class MaterialDatabase:
    def __init__(self, db_path=None, db_url=None):
        self.engine = init_db(db_path=db_path, db_url=db_url)
        self.Session = sessionmaker(bind=self.engine)
        
        session = self.Session()
        try:
            init_default_categories(session)
            _init_default_field_mappings(session)
        finally:
            session.close()
    
    def get_session(self):
        return self.Session()
    
    def get_test_categories(self):
        session = self.Session()
        try:
            categories = session.query(TestCategory).filter_by(is_active=True).order_by(TestCategory.sort_order).all()
            return [
                {
                    'id': c.id,
                    'name': c.name,
                    'code': c.code,
                    'description': c.description
                }
                for c in categories
            ]
        finally:
            session.close()
    
    def get_category_by_code(self, code):
        session = self.Session()
        try:
            category = session.query(TestCategory).filter_by(code=code).first()
            if category:
                return {
                    'id': category.id,
                    'name': category.name,
                    'code': category.code,
                    'fields': [
                        {
                            'id': f.id,
                            'field_name': f.field_name,
                            'field_code': f.field_code,
                            'field_type': f.field_type,
                            'unit': f.unit,
                            'description': f.description,
                            'is_required': f.is_required,
                            'sort_order': f.sort_order
                        }
                        for f in category.field_definitions
                    ]
                }
            return None
        finally:
            session.close()
    
    def check_duplicate(self, spec_data):
        """检查是否存在完全相同的记录
        
        判断完全相同的条件：
        - material_spec_number 相同
        - alloy_grade 相同
        - status 相同
        - specification 相同
        - sampling_direction 相同
        - test_category_code 相同
        - experimental_conditions 相同（从 test_values 中提取）
        
        Returns:
            存在返回已存在记录的 id，不存在返回 None
        """
        session = self.Session()
        try:
            category_code = spec_data.get('test_category_code')
            category = session.query(TestCategory).filter_by(code=category_code).first()
            if not category:
                return None
            
            # 先查找匹配6个基本参数的记录
            existing_specs = session.query(MaterialSpec).filter(
                MaterialSpec.material_spec_number == spec_data.get('material_spec_number'),
                MaterialSpec.alloy_grade == spec_data.get('alloy_grade'),
                MaterialSpec.status == spec_data.get('status'),
                MaterialSpec.specification == spec_data.get('specification'),
                MaterialSpec.sampling_direction == spec_data.get('sampling_direction'),
                MaterialSpec.test_category_id == category.id
            ).all()
            
            if not existing_specs:
                return None
            
            # 提取新数据的 experimental_conditions（从 test_values 中）
            new_experimental_conditions = None
            test_values_input = spec_data.get('test_values', {})
            
            if isinstance(test_values_input, list):
                # 新格式：[{experimental_conditions, values: [...]}]
                for test_category_data in test_values_input:
                    if test_category_data.get('experimental_conditions'):
                        new_experimental_conditions = test_category_data.get('experimental_conditions')
                        break
            else:
                # 旧格式：检查 _experimental_conditions_placeholder
                if '_experimental_conditions_placeholder' in test_values_input:
                    placeholder = test_values_input['_experimental_conditions_placeholder']
                    if isinstance(placeholder, dict) and placeholder.get('experimental_conditions'):
                        new_experimental_conditions = placeholder.get('experimental_conditions')
                else:
                    # 从 test_values 中第一个找到的 experimental_conditions
                    for field_code, value_item in test_values_input.items():
                        if isinstance(value_item, dict) and value_item.get('experimental_conditions'):
                            new_experimental_conditions = value_item.get('experimental_conditions')
                            break
            
            # 如果新数据没有 experimental_conditions，则只检查6个基本参数
            if not new_experimental_conditions:
                return existing_specs[0].id if existing_specs else None
            
            # 将 new_experimental_conditions 转换为 JSON 字符串以便比较
            new_exp_json = json.dumps(new_experimental_conditions, sort_keys=True) if new_experimental_conditions else None
            
            # 检查是否存在匹配基本参数 AND experimental_conditions 的记录
            for spec in existing_specs:
                for tv in spec.test_values:
                    if tv.experimental_conditions:
                        stored_exp_json = json.dumps(json.loads(tv.experimental_conditions), sort_keys=True)
                        if stored_exp_json == new_exp_json:
                            return spec.id
            
            # 找到匹配基本参数的记录，但没有匹配 experimental_conditions 的情况
            # 说明是同一主记录但不同试验条件，不视为重复
            return None
        finally:
            session.close()
    
    def add_spec(self, spec_data, skip_duplicate_check=False):
        session = self.Session()
        try:
            if not skip_duplicate_check:
                duplicate_id = self.check_duplicate(spec_data)
                if duplicate_id:
                    raise ValueError(f"数据已存在，记录ID: {duplicate_id}")
            
            category_code = _normalize_category_code(spec_data.get('test_category_code'))
            spec_data['test_category_code'] = category_code
            category = session.query(TestCategory).filter_by(code=category_code).first()
            if not category:
                raise ValueError(f"测试类别不存在: {category_code}")
            
            required_fields = ['material_spec_number', 'alloy_grade', 'status', 'specification', 'sampling_direction']
            for field in required_fields:
                value = spec_data.get(field)
                if value is None or (isinstance(value, str) and value.strip() == ''):
                    raise ValueError(f"缺少必须字段: {field}")
            
            spec = MaterialSpec(
                material_spec_number=spec_data.get('material_spec_number'),
                alloy_grade=spec_data.get('alloy_grade'),
                status=spec_data.get('status'),
                specification=spec_data.get('specification'),
                sampling_direction=spec_data.get('sampling_direction'),
                test_category_id=category.id,
                additional_conditions=json.dumps(spec_data.get('additional_conditions', {})),
                remarks=spec_data.get('remarks')
            )
            
            field_map = {f.field_code: f for f in category.field_definitions}

            # 聚合未匹配字段到目标 text 字段（如非金属夹杂多个细分字段 → requirement_description）
            _aggregate_orphan_fields(spec_data, field_map)
            
            # 支持两种格式：新格式（数组）和旧格式（字典）
            test_values_input = spec_data.get('test_values', {})
            
            if isinstance(test_values_input, list):
                # 新格式：[{test_category_code, experimental_conditions, values: [{field_code, ...}]}]
                for test_category_data in test_values_input:
                    # 规范化试验条件：未填写温度时默认为"室温"（仅针对温度相关类别）
                    experimental_conditions = test_category_data.get('experimental_conditions', {})
                    experimental_conditions = _normalize_experimental_conditions(experimental_conditions, category_code)
                    test_category_data['experimental_conditions'] = experimental_conditions

                    values = test_category_data.get('values', [])

                    for value_item in values:
                        field_code = value_item.get('field_code')
                        if field_code not in field_map:
                            continue

                        # 跳过空值
                        if not any(value_item.get(k) for k in ['min_value', 'max_value', 'value', 'number_value', 'string_value', 'comparison']):
                            continue

                        field_def = field_map[field_code]
                        raw_unit = value_item.get('unit', field_def.unit)
                        normalized_unit = _normalize_unit(raw_unit, category_code)

                        # 规范化比较符号：>= → ≥，<= → ≤
                        normalized_comparison = _normalize_comparison(value_item.get('comparison'))

                        test_value = TestValue(
                            field_definition_id=field_def.id,
                            unit=normalized_unit,
                            experimental_conditions=json.dumps(experimental_conditions) if experimental_conditions else None
                        )

                        # 保存 item_key（项目关键字）
                        item_key = value_item.get('item_key')
                        if item_key:
                            # 检查是否是不合适的通用关键字（如"化学成分"）
                            if isinstance(item_key, list) and len(item_key) == 1 and item_key[0] in ('化学成分', 'composition', 'chemical'):
                                # 对于化学成分字段，使用元素代码作为 item_key
                                if category_code == 'chemical_composition':
                                    test_value.item_key = _generate_chemical_item_key(field_code)
                                else:
                                    test_value.item_key = json.dumps(item_key)
                            elif isinstance(item_key, str) and item_key.strip() in ('化学成分', 'composition', 'chemical'):
                                # 对于化学成分字段，使用元素代码作为 item_key
                                if category_code == 'chemical_composition':
                                    test_value.item_key = _generate_chemical_item_key(field_code)
                                else:
                                    test_value.item_key = json.dumps([item_key.strip()])
                            else:
                                # 保留原有的 item_key 处理逻辑
                                if isinstance(item_key, list):
                                    test_value.item_key = json.dumps(item_key)
                                elif isinstance(item_key, str) and item_key.strip():
                                    # 逗号分隔的字符串转换为 JSON 数组
                                    keywords = [k.strip() for k in item_key.split(',') if k.strip()]
                                    if keywords:
                                        test_value.item_key = json.dumps(keywords)
                                else:
                                    test_value.item_key = str(item_key)
                        else:
                            # 自动生成 item_key
                            test_value.item_key = generate_item_key(field_def.field_name, None)

                        if field_def.field_type == 'range':
                            if value_item.get('min_value') is not None:
                                test_value.min_value = str(value_item.get('min_value'))
                            elif value_item.get('value') is not None:
                                test_value.min_value = str(value_item.get('value'))

                            if value_item.get('max_value') is not None:
                                test_value.max_value = str(value_item.get('max_value'))
                            elif value_item.get('value') is not None:
                                test_value.max_value = str(value_item.get('value'))

                            test_value.comparison = normalized_comparison
                        elif field_def.field_type == 'number':
                            test_value.number_value = str(value_item.get('value')) if value_item.get('value') is not None else None
                        elif field_def.field_type in ('string', 'text'):
                            test_value.string_value = value_item.get('value')

                        spec.test_values.append(test_value)
            else:
                # 旧格式：{field_code: {...}}
                # 首先检查是否有占位字段中的试验条件
                shared_experimental_conditions = None
                if '_experimental_conditions_placeholder' in test_values_input:
                    placeholder = test_values_input['_experimental_conditions_placeholder']
                    if isinstance(placeholder, dict) and placeholder.get('experimental_conditions'):
                        # 规范化占位符中的试验条件
                        normalized_placeholder_exp = _normalize_experimental_conditions(
                            placeholder['experimental_conditions'], category_code
                        )
                        placeholder['experimental_conditions'] = normalized_placeholder_exp
                        shared_experimental_conditions = normalized_placeholder_exp

                for field_code, value_data in test_values_input.items():
                    if field_code == '_experimental_conditions_placeholder':
                        continue  # 跳过占位字段

                    if field_code not in field_map:
                        continue

                    # 跳过空值（但允许只有 comparison 的情况，如"余量"）
                    if not value_data or (isinstance(value_data, dict) and
                        not any(value_data.get(k) for k in ['min_value', 'max_value', 'value', 'number_value', 'string_value', 'comparison'])):
                        continue

                    field_def = field_map[field_code]
                    raw_unit = value_data.get('unit', field_def.unit)
                    normalized_unit = _normalize_unit(raw_unit, category_code)

                    # 规范化比较符号：>= → ≥，<= → ≤
                    normalized_comparison = _normalize_comparison(value_data.get('comparison'))

                    # 获取 experimental_conditions（优先使用字段自己的，否则使用共享的）
                    experimental_conditions = value_data.get('experimental_conditions', {})
                    if not experimental_conditions and shared_experimental_conditions:
                        experimental_conditions = shared_experimental_conditions
                    # 规范化试验条件：未填写温度时默认为"室温"（仅针对温度相关类别）
                    experimental_conditions = _normalize_experimental_conditions(experimental_conditions, category_code)
                    if isinstance(experimental_conditions, dict) and any(experimental_conditions.values()):
                        experimental_conditions_json = json.dumps(experimental_conditions)
                    else:
                        experimental_conditions_json = None

                    test_value = TestValue(
                        field_definition_id=field_def.id,
                        unit=normalized_unit,
                        experimental_conditions=experimental_conditions_json
                    )

                    # 保存 item_key（项目关键字）
                    item_key = value_data.get('item_key')
                    if item_key:
                        # 检查是否是不合适的通用关键字（如"化学成分"）
                        if isinstance(item_key, list) and len(item_key) == 1 and item_key[0] in ('化学成分', 'composition', 'chemical'):
                            # 对于化学成分字段，使用元素代码作为 item_key
                            if category_code == 'chemical_composition':
                                test_value.item_key = _generate_chemical_item_key(field_code)
                            else:
                                test_value.item_key = json.dumps(item_key)
                        elif isinstance(item_key, str) and item_key.strip() in ('化学成分', 'composition', 'chemical'):
                            # 对于化学成分字段，使用元素代码作为 item_key
                            if category_code == 'chemical_composition':
                                test_value.item_key = _generate_chemical_item_key(field_code)
                            else:
                                test_value.item_key = json.dumps([item_key.strip()])
                        else:
                            # 保留原有的 item_key 处理逻辑
                            if isinstance(item_key, list):
                                test_value.item_key = json.dumps(item_key)
                            elif isinstance(item_key, str) and item_key.strip():
                                # 逗号分隔的字符串转换为 JSON 数组
                                keywords = [k.strip() for k in item_key.split(',') if k.strip()]
                                if keywords:
                                    test_value.item_key = json.dumps(keywords)
                            else:
                                test_value.item_key = str(item_key)
                    else:
                        # 自动生成 item_key
                        test_value.item_key = generate_item_key(field_def.field_name, None)

                    if field_def.field_type == 'range':
                        if value_data.get('min_value') is not None:
                            test_value.min_value = str(value_data.get('min_value'))
                        elif value_data.get('value') is not None:
                            test_value.min_value = str(value_data.get('value'))

                        if value_data.get('max_value') is not None:
                            test_value.max_value = str(value_data.get('max_value'))
                        elif value_data.get('value') is not None:
                            test_value.max_value = str(value_data.get('value'))

                        test_value.comparison = normalized_comparison
                    elif field_def.field_type == 'number':
                        test_value.number_value = str(value_data.get('value')) if value_data.get('value') is not None else None
                    elif field_def.field_type in ('string', 'text'):
                        test_value.string_value = value_data.get('value')

                    spec.test_values.append(test_value)
            
            session.add(spec)
            session.commit()
            return spec.id
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def update_spec(self, spec_id, spec_data):
        session = self.Session()
        try:
            spec = session.query(MaterialSpec).filter_by(id=spec_id).first()
            if not spec:
                raise ValueError(f"规范不存在: {spec_id}")
            
            if 'material_spec_number' in spec_data:
                spec.material_spec_number = spec_data['material_spec_number']
            if 'alloy_grade' in spec_data:
                spec.alloy_grade = spec_data['alloy_grade']
            if 'status' in spec_data:
                spec.status = spec_data['status']
            if 'specification' in spec_data:
                spec.specification = spec_data['specification']
            if 'sampling_direction' in spec_data:
                spec.sampling_direction = spec_data['sampling_direction']
            if 'additional_conditions' in spec_data:
                spec.additional_conditions = json.dumps(spec_data['additional_conditions'])
            if 'remarks' in spec_data:
                spec.remarks = spec_data['remarks']
            
            if 'test_values' in spec_data:
                category = spec.test_category
                field_map = {f.field_code: f for f in category.field_definitions}

                session.query(TestValue).filter_by(spec_id=spec_id).delete()

                # 首先检查是否有占位字段中的试验条件
                shared_experimental_conditions = None
                if '_experimental_conditions_placeholder' in spec_data['test_values']:
                    placeholder = spec_data['test_values']['_experimental_conditions_placeholder']
                    if isinstance(placeholder, dict) and placeholder.get('experimental_conditions'):
                        # 规范化占位符中的试验条件
                        normalized_placeholder_exp = _normalize_experimental_conditions(
                            placeholder['experimental_conditions'], category.code
                        )
                        placeholder['experimental_conditions'] = normalized_placeholder_exp
                        shared_experimental_conditions = normalized_placeholder_exp

                for field_code, value_data in spec_data['test_values'].items():
                    if field_code == '_experimental_conditions_placeholder':
                        continue  # 跳过占位字段

                    if field_code not in field_map:
                        continue

                    # 跳过空值（但允许只有 comparison 的情况，如"余量"）
                    if not value_data or (isinstance(value_data, dict) and
                        not any(value_data.get(k) for k in ['min_value', 'max_value', 'value', 'number_value', 'string_value', 'comparison'])):
                        continue

                    field_def = field_map[field_code]
                    raw_unit = value_data.get('unit', field_def.unit)
                    normalized_unit = _normalize_unit(raw_unit, category.code)

                    # 规范化比较符号：>= → ≥，<= → ≤
                    normalized_comparison = _normalize_comparison(value_data.get('comparison'))

                    # 获取 experimental_conditions（优先使用字段自己的，否则使用共享的）
                    experimental_conditions = value_data.get('experimental_conditions', {})
                    if not experimental_conditions and shared_experimental_conditions:
                        experimental_conditions = shared_experimental_conditions
                    # 规范化试验条件：未填写温度时默认为"室温"（仅针对温度相关类别）
                    experimental_conditions = _normalize_experimental_conditions(experimental_conditions, category.code)
                    if isinstance(experimental_conditions, dict) and any(experimental_conditions.values()):
                        experimental_conditions_json = json.dumps(experimental_conditions)
                    else:
                        experimental_conditions_json = None

                    test_value = TestValue(
                        spec_id=spec_id,
                        field_definition_id=field_def.id,
                        unit=normalized_unit,
                        experimental_conditions=experimental_conditions_json
                    )
                    
                    # 保存 item_key（项目关键字）
                    item_key = value_data.get('item_key')
                    if item_key:
                        # 检查是否是不合适的通用关键字（如"化学成分"）
                        if isinstance(item_key, list) and len(item_key) == 1 and item_key[0] in ('化学成分', 'composition', 'chemical'):
                            # 对于化学成分字段，使用元素代码作为 item_key
                            if category.code == 'chemical_composition':
                                test_value.item_key = _generate_chemical_item_key(field_code)
                            else:
                                test_value.item_key = json.dumps(item_key)
                        elif isinstance(item_key, str) and item_key.strip() in ('化学成分', 'composition', 'chemical'):
                            # 对于化学成分字段，使用元素代码作为 item_key
                            if category.code == 'chemical_composition':
                                test_value.item_key = _generate_chemical_item_key(field_code)
                            else:
                                test_value.item_key = json.dumps([item_key.strip()])
                        else:
                            # 保留原有的 item_key 处理逻辑
                            if isinstance(item_key, list):
                                test_value.item_key = json.dumps(item_key)
                            elif isinstance(item_key, str) and item_key.strip():
                                # 逗号分隔的字符串转换为 JSON 数组
                                keywords = [k.strip() for k in item_key.split(',') if k.strip()]
                                if keywords:
                                    test_value.item_key = json.dumps(keywords)
                            else:
                                test_value.item_key = str(item_key)
                    else:
                        # 自动生成 item_key
                        test_value.item_key = generate_item_key(field_def.field_name, None)
                    
                    if field_def.field_type == 'range':
                        if value_data.get('min_value') is not None:
                            test_value.min_value = str(value_data.get('min_value'))
                        elif value_data.get('value') is not None:
                            test_value.min_value = str(value_data.get('value'))

                        if value_data.get('max_value') is not None:
                            test_value.max_value = str(value_data.get('max_value'))
                        elif value_data.get('value') is not None:
                            test_value.max_value = str(value_data.get('value'))

                        test_value.comparison = normalized_comparison
                    elif field_def.field_type == 'number':
                        test_value.number_value = str(value_data.get('value')) if value_data.get('value') is not None else None
                    elif field_def.field_type in ('string', 'text'):
                        test_value.string_value = value_data.get('value')

                    session.add(test_value)
            
            session.commit()
            return spec.id
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def delete_spec(self, spec_id):
        session = self.Session()
        try:
            spec = session.query(MaterialSpec).filter_by(id=spec_id).first()
            if not spec:
                raise ValueError(f"规范不存在: {spec_id}")
            
            session.delete(spec)
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def query_specs(self, **filters):
        session = self.Session()
        try:
            query = session.query(MaterialSpec)
            
            if 'material_spec_number' in filters and filters['material_spec_number']:
                query = query.filter(MaterialSpec.material_spec_number == filters['material_spec_number'])
            if 'alloy_grade' in filters and filters['alloy_grade']:
                query = query.filter(MaterialSpec.alloy_grade.like(f"%{filters['alloy_grade']}%"))
            if 'status' in filters and filters['status']:
                query = query.filter(MaterialSpec.status.like(f"%{filters['status']}%"))
            if 'specification' in filters and filters['specification']:
                query = query.filter(MaterialSpec.specification == filters['specification'])
            if 'sampling_direction' in filters and filters['sampling_direction']:
                query = query.filter(MaterialSpec.sampling_direction == filters['sampling_direction'])
            if 'test_category_code' in filters and filters['test_category_code']:
                category = session.query(TestCategory).filter_by(code=filters['test_category_code']).first()
                if category:
                    query = query.filter(MaterialSpec.test_category_id == category.id)
            
            # 处理 update_time 过滤（查询指定时间之后更新的记录）
            update_time = filters.get('update_time')
            if update_time:
                try:
                    from datetime import datetime
                    update_dt = datetime.strptime(update_time, '%Y-%m-%d %H:%M:%S')
                    query = query.filter(MaterialSpec.updated_at >= update_dt)
                except ValueError:
                    try:
                        from datetime import datetime
                        update_dt = datetime.strptime(update_time, '%Y-%m-%d')
                        query = query.filter(MaterialSpec.updated_at >= update_dt)
                    except ValueError:
                        pass
            
            # 处理 experimental_conditions 过滤（支持模糊匹配）
            experimental_conditions = filters.get('experimental_conditions')
            if experimental_conditions:
                # 获取所有 test_values 记录，并过滤匹配的记录
                all_test_values = session.query(TestValue).all()
                matching_spec_ids = set()
                
                for tv in all_test_values:
                    if not tv.experimental_conditions:
                        continue
                    try:
                        stored_conditions = json.loads(tv.experimental_conditions)
                        # 检查是否包含所有指定的 experimental_conditions
                        if all(stored_conditions.get(k) == v for k, v in experimental_conditions.items() if v):
                            matching_spec_ids.add(tv.spec_id)
                    except json.JSONDecodeError:
                        continue
                
                if matching_spec_ids:
                    query = query.filter(MaterialSpec.id.in_(matching_spec_ids))
                else:
                    # 没有匹配的记录，返回空结果
                    return []
            
            specs = query.order_by(MaterialSpec.created_at.desc()).all()
            
            result = []
            for spec in specs:
                test_values = {}
                for tv in spec.test_values:
                    if not tv.field_definition:
                        continue
                    field_code = tv.field_definition.field_code
                    if tv.field_definition.field_type == 'range':
                        test_values[field_code] = {
                            'min_value': _format_number(tv.min_value),
                            'max_value': _format_number(tv.max_value),
                            'comparison': tv.comparison,
                            'unit': tv.unit,
                            'field_name': tv.field_definition.field_name,
                            'item_key': json.loads(tv.item_key) if tv.item_key else [],
                            'experimental_conditions': json.loads(tv.experimental_conditions) if tv.experimental_conditions else {}
                        }
                    elif tv.field_definition.field_type == 'number':
                        test_values[field_code] = {
                            'value': _format_number(tv.number_value),
                            'unit': tv.unit,
                            'field_name': tv.field_definition.field_name,
                            'item_key': json.loads(tv.item_key) if tv.item_key else [],
                            'experimental_conditions': json.loads(tv.experimental_conditions) if tv.experimental_conditions else {}
                        }
                    else:
                        test_values[field_code] = {
                            'value': tv.string_value,
                            'field_name': tv.field_definition.field_name,
                            'item_key': json.loads(tv.item_key) if tv.item_key else [],
                            'experimental_conditions': json.loads(tv.experimental_conditions) if tv.experimental_conditions else {}
                        }
                
                spec_dict = {
                    'id': spec.id,
                    'spec_number': spec.material_spec_number,
                    'alloy_grade': spec.alloy_grade,
                    'status': spec.status,
                    'specification': spec.specification,
                    'sampling_direction': spec.sampling_direction,
                    'test_category': {
                        'id': spec.test_category.id,
                        'name': spec.test_category.name,
                        'code': spec.test_category.code
                    },
                    'test_values': test_values,
                    'additional_conditions': json.loads(spec.additional_conditions) if spec.additional_conditions else {},
                    'remarks': spec.remarks,
                    'created_at': spec.created_at.strftime('%Y-%m-%d %H:%M:%S') if spec.created_at else None,
                    'updated_at': spec.updated_at.strftime('%Y-%m-%d %H:%M:%S') if spec.updated_at else None
                }
                result.append(spec_dict)
            
            return result
        finally:
            session.close()
    
    def get_all_alloy_grades(self):
        session = self.Session()
        try:
            grades = session.query(MaterialSpec.alloy_grade).distinct().all()
            return [g[0] for g in grades]
        finally:
            session.close()
    
    def get_all_spec_numbers(self):
        session = self.Session()
        try:
            numbers = session.query(MaterialSpec.material_spec_number).distinct().all()
            return [n[0] for n in numbers]
        finally:
            session.close()
    
    def get_statistics(self):
        session = self.Session()
        try:
            total_count = session.query(MaterialSpec).count()
            alloy_grades = session.query(MaterialSpec.alloy_grade).distinct().count()
            # 统计实际有数据的测试类别数（而不是所有类别模板）
            categories = session.query(MaterialSpec.test_category_id).distinct().count()
            
            return {
                'total_count': total_count,
                'alloy_grades': alloy_grades,
                'categories': categories
            }
        finally:
            session.close()
    
    def add_custom_test_category(self, name, code, fields, description=None):
        session = self.Session()
        try:
            existing = session.query(TestCategory).filter_by(code=code).first()
            if existing:
                raise ValueError(f"测试类别代码已存在: {code}")
            
            category = TestCategory(name=name, code=code, description=description)
            session.add(category)
            session.flush()
            
            for i, field_data in enumerate(fields):
                field = TestFieldDefinition(
                    category_id=category.id,
                    field_name=field_data['field_name'],
                    field_code=field_data['field_code'],
                    field_type=field_data['field_type'],
                    unit=field_data.get('unit'),
                    description=field_data.get('description'),
                    is_required=field_data.get('is_required', False),
                    sort_order=i
                )
                session.add(field)
            
            session.commit()
            return category.id
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def get_all_test_categories(self):
        session = self.Session()
        try:
            categories = session.query(TestCategory).order_by(TestCategory.sort_order).all()
            return [
                {
                    'id': c.id,
                    'name': c.name,
                    'code': c.code,
                    'description': c.description,
                    'is_active': c.is_active,
                    'sort_order': c.sort_order,
                    'fields': [
                        {
                            'id': f.id,
                            'field_name': f.field_name,
                            'field_code': f.field_code,
                            'field_type': f.field_type,
                            'unit': f.unit,
                            'description': f.description,
                            'is_required': f.is_required,
                            'sort_order': f.sort_order
                        }
                        for f in c.field_definitions
                    ]
                }
                for c in categories
            ]
        finally:
            session.close()
    
    def update_test_category(self, category_id, name=None, code=None, description=None, is_active=None, sort_order=None):
        session = self.Session()
        try:
            category = session.query(TestCategory).filter_by(id=category_id).first()
            if not category:
                raise ValueError(f"测试类别不存在: {category_id}")
            
            if name is not None:
                category.name = name
            if code is not None:
                existing = session.query(TestCategory).filter_by(code=code).filter(TestCategory.id != category_id).first()
                if existing:
                    raise ValueError(f"测试类别代码已存在: {code}")
                category.code = code
            if description is not None:
                category.description = description
            if is_active is not None:
                category.is_active = is_active
            if sort_order is not None:
                category.sort_order = sort_order
            
            session.commit()
            return category.id
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def delete_test_category(self, category_id):
        session = self.Session()
        try:
            category = session.query(TestCategory).filter_by(id=category_id).first()
            if not category:
                raise ValueError(f"测试类别不存在：{category_id}")
            
            session.delete(category)
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def get_test_category_fields(self, category_id):
        """获取测试类别的所有字段定义"""
        session = self.Session()
        try:
            fields = session.query(TestFieldDefinition).filter_by(category_id=category_id).order_by(TestFieldDefinition.sort_order).all()
            result = []
            for field in fields:
                result.append({
                    'id': field.id,
                    'category_id': field.category_id,
                    'field_name': field.field_name,
                    'field_code': field.field_code,
                    'field_type': field.field_type,
                    'unit': field.unit,
                    'description': field.description,
                    'is_required': field.is_required,
                    'sort_order': field.sort_order
                })
            return result
        finally:
            session.close()
    
    def add_test_field(self, category_id, field_name, field_code, field_type, unit=None, description=None, is_required=False, sort_order=0):
        session = self.Session()
        try:
            category = session.query(TestCategory).filter_by(id=category_id).first()
            if not category:
                raise ValueError(f"测试类别不存在: {category_id}")
            
            existing = session.query(TestFieldDefinition).filter_by(
                category_id=category_id,
                field_code=field_code
            ).first()
            if existing:
                raise ValueError(f"字段代码已存在: {field_code}")
            
            field = TestFieldDefinition(
                category_id=category_id,
                field_name=field_name,
                field_code=field_code,
                field_type=field_type,
                unit=unit,
                description=description,
                is_required=is_required,
                sort_order=sort_order
            )
            session.add(field)
            session.commit()
            return field.id
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def update_test_field(self, field_id, field_name=None, field_code=None, field_type=None, unit=None, description=None, is_required=None, sort_order=None):
        session = self.Session()
        try:
            field = session.query(TestFieldDefinition).filter_by(id=field_id).first()
            if not field:
                raise ValueError(f"字段不存在: {field_id}")
            
            if field_name is not None:
                field.field_name = field_name
            if field_code is not None:
                existing = session.query(TestFieldDefinition).filter_by(
                    category_id=field.category_id,
                    field_code=field_code
                ).filter(TestFieldDefinition.id != field_id).first()
                if existing:
                    raise ValueError(f"字段代码已存在: {field_code}")
                field.field_code = field_code
            if field_type is not None:
                field.field_type = field_type
            if unit is not None:
                field.unit = unit
            if description is not None:
                field.description = description
            if is_required is not None:
                field.is_required = is_required
            if sort_order is not None:
                field.sort_order = sort_order
            
            session.commit()
            return field.id
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def delete_test_field(self, field_id):
        session = self.Session()
        try:
            field = session.query(TestFieldDefinition).filter_by(id=field_id).first()
            if not field:
                raise ValueError(f"字段不存在: {field_id}")
            
            session.delete(field)
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def get_field_mappings(self, category_code=None, active_only=True, source_field=None, target_field_code=None, merge_sources=True):
        session = self.Session()
        try:
            query = session.query(FieldMapping)
            if category_code:
                query = query.filter_by(category_code=category_code)
            if active_only:
                query = query.filter_by(is_active=True)
            if source_field:
                query = query.filter(FieldMapping.source_field.like(f'%{source_field}%'))
            if target_field_code:
                query = query.filter(FieldMapping.target_field_code.like(f'%{target_field_code}%'))
            
            mappings = query.order_by(FieldMapping.target_field_code, FieldMapping.source_field).all()
            
            if merge_sources:
                merged = {}
                for m in mappings:
                    key = (m.target_field_code, m.category_code)
                    if key not in merged:
                        try:
                            category_name = m.category.name if m.category else '通用'
                        except Exception:
                            category_name = '通用'
                        merged[key] = {
                            'id': m.id,
                            'source_fields': [m.source_field],
                            'target_field_code': m.target_field_code,
                            'category_code': m.category_code,
                            'category_name': category_name,
                            'is_active': m.is_active,
                            'created_at': m.created_at.strftime('%Y-%m-%d %H:%M:%S') if m.created_at else None
                        }
                    else:
                        if m.source_field not in merged[key]['source_fields']:
                            merged[key]['source_fields'].append(m.source_field)
                            merged[key]['source_fields'].sort()
                return list(merged.values())
            
            result = []
            for m in mappings:
                try:
                    category_name = m.category.name if m.category else '通用'
                except Exception as e:
                    category_name = '通用'
                result.append({
                    'id': m.id,
                    'source_field': m.source_field,
                    'target_field_code': m.target_field_code,
                    'category_code': m.category_code,
                    'category_name': category_name,
                    'is_active': m.is_active,
                    'created_at': m.created_at.strftime('%Y-%m-%d %H:%M:%S') if m.created_at else None
                })
            return result
        finally:
            session.close()
    
    def add_field_mapping(self, source_fields, target_field_code, category_code=None):
        session = self.Session()
        try:
            if isinstance(source_fields, str):
                source_fields = [source_fields]
            
            for source_field in source_fields:
                mapping = FieldMapping(
                    source_field=source_field,
                    target_field_code=target_field_code,
                    category_code=category_code
                )
                session.add(mapping)
            
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def update_field_mapping(self, mapping_id, source_fields=None, target_field_code=None, category_code=None, is_active=None):
        session = self.Session()
        try:
            existing = session.query(FieldMapping).filter_by(id=mapping_id).first()
            if not existing:
                raise ValueError(f"字段映射不存在：{mapping_id}")
            
            if source_fields is not None or target_field_code is not None:
                if source_fields is None:
                    source_fields = [existing.source_field]
                elif isinstance(source_fields, str):
                    source_fields = [source_fields]
                
                target_code = target_field_code if target_field_code else existing.target_field_code
                cat_code = category_code if category_code is not None else existing.category_code
                
                session.query(FieldMapping).filter(
                    FieldMapping.target_field_code == target_code,
                    FieldMapping.category_code == cat_code
                ).delete()
                
                for source_field in source_fields:
                    mapping = FieldMapping(
                        source_field=source_field,
                        target_field_code=target_code,
                        category_code=cat_code,
                        is_active=is_active if is_active is not None else existing.is_active
                    )
                    session.add(mapping)
            else:
                if target_field_code is not None:
                    existing.target_field_code = target_field_code
                if category_code is not None:
                    existing.category_code = category_code
                if is_active is not None:
                    existing.is_active = is_active
            
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def delete_field_mapping(self, mapping_id):
        session = self.Session()
        try:
            mapping = session.query(FieldMapping).filter_by(id=mapping_id).first()
            if not mapping:
                raise ValueError(f"字段映射不存在：{mapping_id}")
            
            session.delete(mapping)
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def apply_field_mappings(self, test_values: dict, category_code: str = None) -> dict:
        session = self.Session()
        try:
            mappings = session.query(FieldMapping).filter_by(is_active=True).all()
            if category_code:
                category_mappings = [m for m in mappings if m.category_code == category_code or m.category_code is None]
            else:
                category_mappings = mappings
            
            mapping_dict = {m.source_field: m.target_field_code for m in category_mappings}
            mapping_dict_lower = {m.source_field.lower(): m.target_field_code for m in category_mappings}
            
            result = {}
            for field_key, value_data in test_values.items():
                field_key_lower = field_key.lower()
                
                if field_key in mapping_dict:
                    target_code = mapping_dict[field_key]
                    result[target_code] = value_data
                elif field_key_lower in mapping_dict_lower:
                    target_code = mapping_dict_lower[field_key_lower]
                    result[target_code] = value_data
                else:
                    result[field_key] = value_data
            
            return result
        finally:
            session.close()
