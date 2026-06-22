"""
JSON 导入数据转换工具
将外部 JSON 数据转换为与材料规范数据库匹配的结构
"""
import json
from typing import List, Dict, Any

class ImportDataConverter:
    """导入数据转换器"""
    
    REQUIRED_FIELDS = ['material_spec_number', 'alloy_grade', 'status', 'specification', 'sampling_direction']
    
    def __init__(self):
        self.element_map = {
            'c': 'C', 'cr': 'Cr', 'mo': 'Mo', 'al': 'Al', 'ti': 'Ti',
            'co': 'Co', 'b': 'B', 'ni': 'Ni', 'si': 'Si', 'mn': 'Mn',
            's': 'S', 'p': 'P', 'zr': 'Zr', 'cu': 'Cu', 'fe': 'Fe',
            'pb': 'Pb', 'as': 'As', 'sn': 'Sn', 'sb': 'Sb', 'bi': 'Bi',
            'ag': 'Ag', 'v': 'V', 'w': 'W', 'nb': 'Nb', 'ta': 'Ta',
            're': 'Re', 'la': 'La', 'ce': 'Ce', 'y': 'Y'
        }
        self.element_field_codes = {
            'C': 'c', 'Cr': 'cr', 'Mo': 'mo', 'Al': 'al', 'Ti': 'ti',
            'Co': 'co', 'B': 'b', 'Ni': 'ni', 'Si': 'si', 'Mn': 'mn',
            'S': 's', 'P': 'p', 'Zr': 'zr', 'Cu': 'cu', 'Fe': 'fe',
            'Pb': 'pb', 'As': 'as', 'Sn': 'sn', 'Sb': 'sb', 'Bi': 'bi',
            'Ag': 'ag', 'V': 'v', 'W': 'w', 'Nb': 'nb', 'Ta': 'ta',
            'Re': 're', 'La': 'la', 'Ce': 'ce', 'Y': 'y'
        }
    
    def convert(self, data: Any) -> List[Dict]:
        """
        转换 JSON 数据为数据库格式
        
        Args:
            data: 输入的 JSON 数据，可以是 dict 或 list
        
        Returns:
            转换后的数据列表
        """
        if isinstance(data, dict):
            return self._convert_single(data)
        elif isinstance(data, list):
            result = []
            for item in data:
                converted = self._convert_single(item)
                result.extend(converted)
            return result
        else:
            raise ValueError("输入数据必须是 dict 或 list")
    
    def _convert_single(self, data: Dict) -> List[Dict]:
        """转换单个数据对象"""
        specs = []
        
        test_category_code = self._detect_category(data)
        
        test_values = self._extract_test_values(data, test_category_code)
        
        spec = {
            'material_spec_number': self._get_field(data, 'spec_number', ['material_spec_number', '标准号', '标准编号', 'standard', 'standard_number']),
            'alloy_grade': self._get_field(data, 'alloy_grade', ['牌号', 'grade', 'material_grade']),
            'status': self._get_field(data, 'status', ['状态', 'state', 'condition']),
            'specification': self._get_field(data, 'specification', ['规格', 'size', 'dimension'], '-'),
            'sampling_direction': self._get_field(data, 'sampling_direction', ['取样方向', 'direction'], '-'),
            'test_category_code': test_category_code,
            'test_values': test_values,
            'additional_conditions': self._extract_additional_conditions(data),
            'remarks': self._get_field(data, 'remarks', ['备注', 'note', 'remark'])
        }
        
        specs.append(spec)
        return specs
    
    def _detect_category(self, data: Dict) -> str:
        """检测测试类别"""
        category_keywords = {
            'chemical_composition': ['化学成分', 'composition', 'chemical', '元素'],
            'tension': ['拉伸', 'tension', 'tensile'],
            'impact': ['冲击', 'impact', 'charpy'],
            'stress_rupture': ['持久', 'rupture', 'stress_rupture'],
            'creep': ['蠕变', 'creep'],
            'hardness': ['硬度', 'hardness', 'hrc', 'hb', 'hv'],
        }
        
        category_code = data.get('test_category_code')
        if category_code:
            return category_code
        
        test_values = data.get('test_values', {})
        for code, keywords in category_keywords.items():
            for key in test_values.keys():
                if any(kw.lower() in key.lower() for kw in keywords):
                    return code
        
        if any(elem.upper() in self.element_map.values() for elem in test_values.keys()):
            return 'chemical_composition'
        
        return 'chemical_composition'
    
    def _extract_test_values(self, data: Dict, category_code: str) -> Dict:
        """提取测试值"""
        test_values = {}
        
        raw_values = data.get('test_values', {})
        
        if not raw_values:
            for key, value in data.items():
                if key not in self.REQUIRED_FIELDS and key not in ['test_category_code', 'additional_conditions', 'remarks']:
                    if isinstance(value, (dict, str, int, float)):
                        raw_values[key] = value
        
        for key, value in raw_values.items():
            normalized_key = self._normalize_element_key(key)
            normalized_field_code = self._normalize_field_code(key)
            
            if isinstance(value, dict):
                test_values[normalized_field_code] = self._normalize_value(value)
            elif isinstance(value, str):
                test_values[normalized_field_code] = self._parse_string_value(value)
            elif isinstance(value, (int, float)):
                test_values[normalized_field_code] = {'value': str(value)}
        
        return test_values
    
    def _normalize_element_key(self, key: str) -> str:
        """标准化元素键名"""
        key_lower = key.lower().strip()
        
        if key_lower in self.element_map:
            return self.element_map[key_lower]
        
        if key.upper() in self.element_map.values():
            return key.upper()
        
        return key
    
    def _normalize_field_code(self, key: str) -> str:
        """标准化元素的 field_code（数据库使用小写）"""
        key_upper = key.strip()
        key_lower = key.lower().strip()
        
        if key_upper in self.element_field_codes:
            return self.element_field_codes[key_upper]
        
        return key_lower
    
    def _normalize_value(self, value: Dict) -> Dict:
        """标准化值格式"""
        result = {}
        
        if 'min_value' in value:
            result['min_value'] = str(value['min_value'])
        if 'max_value' in value:
            result['max_value'] = str(value['max_value'])
        if 'value' in value:
            result['value'] = str(value['value'])
        if 'comparison' in value:
            result['comparison'] = value['comparison']
        if 'unit' in value:
            result['unit'] = value['unit']
        
        # 保留 item_key 字段（项目关键字数组）
        if 'item_key' in value and value['item_key']:
            result['item_key'] = value['item_key']
        
        # 保留 experimental_conditions 字段（试验条件）
        if 'experimental_conditions' in value and value['experimental_conditions']:
            result['experimental_conditions'] = value['experimental_conditions']
        
        if 'min_value' not in result and 'max_value' not in result and 'value' not in result:
            result['value'] = json.dumps(value, ensure_ascii=False)
        
        return result
    
    def _parse_string_value(self, value: str) -> Dict:
        """解析字符串值"""
        value = value.strip()
        
        import re
        
        range_match = re.match(r'^([≤≥<>=]?)\s*(\d+\.?\d*)\s*~\s*([≤≥<>=]?)\s*(\d+\.?\d*)$', value)
        if range_match:
            return {
                'min_value': range_match.group(2),
                'max_value': range_match.group(4)
            }
        
        comp_match = re.match(r'^([≤≥<>=]+)\s*(\d+\.?\d*)$', value)
        if comp_match:
            return {
                'comparison': comp_match.group(1),
                'value': comp_match.group(2)
            }
        
        return {'value': value}
    
    def _get_field(self, data: Dict, field: str, alternatives: List[str], default=None):
        """获取字段值"""
        if field in data and data[field]:
            return data[field]
        
        for alt in alternatives:
            if alt in data and data[alt]:
                return data[alt]
        
        return default
    
    def _extract_additional_conditions(self, data: Dict) -> Dict:
        """提取附加条件"""
        conditions = {}
        
        if 'additional_conditions' in data:
            if isinstance(data['additional_conditions'], dict):
                conditions = data['additional_conditions']
        
        return conditions


def convert_import_data(data: Any) -> List[Dict]:
    """
    转换导入数据
    
    Args:
        data: 输入的 JSON 数据
    
    Returns:
        转换后的数据列表
    """
    converter = ImportDataConverter()
    return converter.convert(data)


if __name__ == '__main__':
    test_data = {
        "material_spec_number": "GB/T 12345-2020",
        "alloy_grade": "304",
        "status": "固溶",
        "test_values": {
            "C": {"min_value": "0.015", "max_value": "0.060"},
            "cr": {"min_value": "17.0", "max_value": "21.0"}
        }
    }
    
    result = convert_import_data(test_data)
    print(json.dumps(result, ensure_ascii=False, indent=2))
