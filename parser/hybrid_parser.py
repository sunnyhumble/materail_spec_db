import base64
import io
import json
import time
import re
import logging
from PIL import Image
from typing import List, Dict
from openai import OpenAI

logger = logging.getLogger(__name__)

class HybridMaterialParser:
    def __init__(self, api_key: str, base_url: str = "https://api.openai.com/v1", model: str = "gpt-4o"):
        from paddleocr import PaddleOCR
        self.ocr = PaddleOCR(use_angle_cls=True, lang='ch')
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        logger.info(f"[初始化] HybridMaterialParser 初始化完成，OCR: PaddleOCR, LLM: {model}")

    def parse_image_from_base64(self, base64_data: str, test_category_code: str = None) -> List[Dict]:
        ocr_start = time.time()
        
        if ',' in base64_data:
            base64_data = base64_data.split(',')[1]

        try:
            image_data = base64.b64decode(base64_data)
            image = Image.open(io.BytesIO(image_data))
            
            temp_buffer = io.BytesIO()
            image.save(temp_buffer, format='PNG')
            temp_buffer.seek(0)

            result = self.ocr.ocr(temp_buffer.getvalue(), cls=True)

            if not result or not result[0]:
                logger.warning("[Hybrid] OCR 未识别到内容")
                return []

            texts = []
            for line in result[0]:
                text = line[1][0]
                confidence = line[1][1]
                texts.append({'text': text, 'confidence': confidence})

            ocr_elapsed = time.time() - ocr_start
            logger.info(f"[性能] PaddleOCR 识别完成，耗时：{ocr_elapsed:.2f}秒，识别到 {len(texts)} 个文本区域")
            
            logger.info(f"[OCR] 原始识别文本：{json.dumps(texts, ensure_ascii=False)}")
            
            # 规则预处理：提取元素 - 数值对
            extracted_data = self._extract_elements_by_rules(texts)
            elements_count = len(extracted_data.get('elements', []))
            print(f"[规则提取] 找到 {elements_count} 个元素")
            logger.info(f"[Hybrid] 规则提取得到 {elements_count} 个元素")
            
            # 如果规则提取成功，直接让 LLM 格式化
            if elements_count > 0:
                print(f"[路径] 使用 _format_with_llm 路径")
                specs = self._format_with_llm(extracted_data, test_category_code)
            else:
                # 规则提取失败，使用完整文本让 LLM 处理
                print(f"[路径] 使用 _parse_with_llm 路径")
                recognized_text = '\n'.join([t['text'] for t in texts])
                specs = self._parse_with_llm(recognized_text, test_category_code)
            
            # **关键优化**：后处理 - 按测试类别强制拆分数据
            print(f"================ [拆分前] 原始数据条数：{len(specs)} ================")
            logger.info(f"[拆分前] 原始数据条数：{len(specs)}")
            if specs and len(specs) > 0:
                first_spec_fields = list(specs[0].get('test_values', {}).keys())
                print(f"[拆分前] 第一条数据字段：{first_spec_fields}")
                logger.info(f"[拆分前] 数据字段：{first_spec_fields}")
            
            # **修复**：将 additional_conditions 中的 test_temperature 移动到 test_values
            for spec in specs:
                additional = spec.get('additional_conditions', {})
                test_values = spec.get('test_values', {})
                
                # 检查 additional_conditions 中是否有 test_temperature
                if 'test_temperature' in additional:
                    print(f"[修复] 发现 test_temperature 在 additional_conditions 中，移动到 test_values")
                    logger.info(f"[修复] 将 test_temperature 从 additional_conditions 移动到 test_values")
                    test_values['test_temperature'] = additional.pop('test_temperature')
                    spec['test_values'] = test_values
                    spec['additional_conditions'] = additional
            
            # **持久试验合并**：将同一 material_spec_number 的 creep 和 tension 数据合并（如果 tension 包含持久试验字段）
            specs = self._merge_creep_specs(specs)
            
            # **晶粒度特殊处理**：拆分预处理、规格、判定要求，生成多条记录
            try:
                specs = self._process_grain_size_specs(specs)
                print(f"[晶粒度处理后] 数据条数：{len(specs)}")
                logger.info(f"[晶粒度] 处理后得到 {len(specs)} 条数据")
            except Exception as grain_err:
                print(f"[晶粒度处理错误] {grain_err}")
                logger.error(f"[晶粒度] 处理失败：{grain_err}")
            
            try:
                specs = self._split_specs_by_category(specs)
                print(f"[拆分后] 数据条数：{len(specs)}")
                logger.info(f"[Hybrid] 后处理后得到 {len(specs)} 条数据")
            except Exception as split_err:
                print(f"[拆分错误] {split_err}")
                logger.error(f"[拆分] 拆分失败：{split_err}", exc_info=True)
                # 拆分失败时，不改变原始数据

            # **兜底拆分**：对 grain_size_description / macro_structure_description 等 text 字段
            # 检测 value 字段中是否包含多个"直径"规格，若是则拆成多条
            try:
                specs = self._split_text_field_specs(specs)
                print(f"[text字段拆分后] 数据条数：{len(specs)}")
                logger.info(f"[text字段拆分] 处理后得到 {len(specs)} 条数据")
            except Exception as text_err:
                print(f"[text字段拆分错误] {text_err}")
                logger.error(f"[text字段拆分] 拆分失败：{text_err}", exc_info=True)

            # **规范化输出**：comparison 符号标准化 + 试验条件默认室温
            try:
                from database.operations import (
                    _normalize_category_code as _norm_cat,
                    _normalize_comparison as _norm_cmp,
                    _normalize_experimental_conditions as _norm_exp,
                )
                for spec in specs:
                    # 类别代码别名映射（LLM 常见拼写错误 → 数据库标准代码）
                    spec['test_category_code'] = _norm_cat(spec.get('test_category_code', ''))
                    cat = spec['test_category_code']
                    tv = spec.get('test_values', {})
                    if isinstance(tv, dict):
                        for field_code, field_data in tv.items():
                            if not isinstance(field_data, dict):
                                continue
                            if 'comparison' in field_data:
                                field_data['comparison'] = _norm_cmp(field_data.get('comparison'))
                            if 'experimental_conditions' in field_data:
                                field_data['experimental_conditions'] = _norm_exp(
                                    field_data.get('experimental_conditions', {}), cat
                                )
                    elif isinstance(tv, list):
                        for group in tv:
                            if not isinstance(group, dict):
                                continue
                            group['experimental_conditions'] = _norm_exp(
                                group.get('experimental_conditions', {}), cat
                            )
                            for value_item in group.get('values', []) or []:
                                if not isinstance(value_item, dict):
                                    continue
                                if 'comparison' in value_item:
                                    value_item['comparison'] = _norm_cmp(value_item.get('comparison'))
            except Exception as norm_err:
                print(f"[规范化错误] {norm_err}")
                logger.error(f"[规范化] 规范化失败：{norm_err}", exc_info=True)

            total_elapsed = time.time() - ocr_start
            if specs:
                logger.info(f"[性能] 处理完成，总耗时：{total_elapsed:.2f}秒")
                logger.info(f"[Hybrid] 解析到 {len(specs)} 条数据")
            else:
                logger.warning(f"[性能] 识别失败，总耗时：{total_elapsed:.2f}秒")
            
            return specs

        except Exception as e:
            logger.error(f"[Hybrid] 识别失败：{e}", exc_info=True)
            return []

    def _extract_elements_by_rules(self, texts: List[Dict]) -> Dict:
        """使用规则快速提取元素和数值 - 优化版"""
        element_map = {
            'C': 'C', 'CR': 'Cr', 'NB': 'Nb', 'MG': 'Mg', 'CU': 'Cu', 'B': 'B',
            'MN': 'Mn', 'SI': 'Si', 'NI': 'Ni', 'MO': 'Mo', 'AL': 'Al', 'TI': 'Ti',
            'CO': 'Co', 'S': 'S', 'P': 'P', 'ZR': 'Zr', 'FE': 'Fe', 'PB': 'Pb',
            'AS': 'As', 'SN': 'Sn', 'SB': 'Sb', 'BI': 'Bi', 'AG': 'Ag', 'V': 'V',
            'W': 'W'
        }
        
        # 特殊字段映射（拉伸、冲击、断裂韧度等）
        special_fields = {
            # 抗拉强度
            'σB': 'σ_b', 'ΣB': 'σ_b', 'SIGMAB': 'σ_b', '抗拉强度': 'σ_b',
            'ΣB': 'σ_b', 'SB': 'σ_b', 'SIGMA B': 'σ_b',
            # 屈服强度
            'Σ0.2': 'σ_0.2', 'Σ0': 'σ_0.2', 'SIGMA0.2': 'σ_0.2', '屈服强度': 'σ_0.2',
            'S0.2': 'σ_0.2', 'SIGMA 0.2': 'σ_0.2',
            # 断后伸长率 (elongation) - 各种符号和后缀
            '断后伸长率': 'elongation', '断后伸长率A': 'elongation', 'elongation': 'elongation', 'elong': 'elongation',
            'δ': 'elongation', 'δA': 'elongation', 'Δ': 'elongation', 'ΔA': 'elongation',
            'delta': 'elongation', 'DELTA': 'elongation',
            # 带后缀4 (短比例试样)
            '断后伸长率4': 'elongation_4d', '断后伸长率4d': 'elongation_4d', '断后伸长率4D': 'elongation_4d',
            'δ4': 'elongation_4d', 'δ_4': 'elongation_4d', 'Δ4': 'elongation_4d', 'Δ_4': 'elongation_4d',
            'delta4': 'elongation_4d', 'delta_4': 'elongation_4d', 'DELTA4': 'elongation_4d', 'DELTA_4': 'elongation_4d',
            'elongation_4d': 'elongation_4d', 'elong_4d': 'elongation_4d',
            # 带后缀5 (长比例试样)
            '断后伸长率5': 'elongation_5d', '断后伸长率5d': 'elongation_5d', '断后伸长率5D': 'elongation_5d',
            'δ5': 'elongation_5d', 'δ_5': 'elongation_5d', 'Δ5': 'elongation_5d', 'Δ_5': 'elongation_5d',
            'delta5': 'elongation_5d', 'delta_5': 'elongation_5d', 'DELTA5': 'elongation_5d', 'DELTA_5': 'elongation_5d',
            'elongation_5d': 'elongation_5d', 'elong_5d': 'elongation_5d',
            # 带后缀10 (超长比例试样)
            '断后伸长率10': 'elongation_10d', '断后伸长率10d': 'elongation_10d',
            'δ10': 'elongation_10d', 'δ_10': 'elongation_10d', 'Δ10': 'elongation_10d', 'Δ_10': 'elongation_10d',
            'delta10': 'elongation_10d', 'delta_10': 'elongation_10d', 'DELTA10': 'elongation_10d', 'DELTA_10': 'elongation_10d',
            'elongation_10d': 'elongation_10d', 'elong_10d': 'elongation_10d',
            # 带后缀11 (特殊比例试样)
            '断后伸长率11': 'elongation_11d', '断后伸长率11d': 'elongation_11d',
            'δ11': 'elongation_11d', 'δ_11': 'elongation_11d', 'Δ11': 'elongation_11d', 'Δ_11': 'elongation_11d',
            'delta11': 'elongation_11d', 'delta_11': 'elongation_11d', 'DELTA11': 'elongation_11d', 'DELTA_11': 'elongation_11d',
            'elongation_11d': 'elongation_11d', 'elong_11d': 'elongation_11d',
            # 断面收缩率
            'Ψ': 'ψ', 'PSI': 'ψ', '断面收缩率': 'ψ',
            # 冲击吸收能量
            'AKU2': 'A_Ku2', 'A_KU2': 'A_Ku2', '冲击吸收能量': 'A_Ku2',
            'AKU': 'A_Ku2', 'KU2': 'A_Ku2',
            # 断裂韧度
            'KIC': 'K_IC', 'K_IC': 'K_IC', 'K1C': 'K_IC', '断裂韧度': 'K_IC',
            'K IC': 'K_IC', 'K I C': 'K_IC',
            # 硬度标尺 (HRC/HB/HV/HBW/HRA/HRB 等)
            'HRC': 'hardness_value', 'HRC0': 'hardness_value', 'HRC值': 'hardness_value',
            'HB': 'hardness_value', 'HBW': 'hardness_value', 'HBW5/750': 'hardness_value',
            'HV': 'hardness_value', 'HV1': 'hardness_value', 'HV5': 'hardness_value',
            'HV10': 'hardness_value', 'HV30': 'hardness_value', 'HV50': 'hardness_value',
            'HRA': 'hardness_value', 'HRB': 'hardness_value', 'HRD': 'hardness_value',
            'HRE': 'hardness_value', 'HRF': 'hardness_value', 'HRG': 'hardness_value',
            'HR15N': 'hardness_value', 'HR30N': 'hardness_value', 'HR45N': 'hardness_value',
            'HRC硬度': 'hardness_value', '硬度': 'hardness_value',
            '硬度值': 'hardness_value', 'HARDNESS': 'hardness_value',
        }
        
        import re
        
        # 步骤 1: 找出所有元素位置
        elements_pos = []
        special_fields_found = []
        for i, text in enumerate(texts):
            txt = text['text'].upper().strip()
            original_txt = text['text'].strip()
            
            # 检查化学元素
            if txt in element_map:
                elements_pos.append({'index': i, 'element': element_map[txt], 'type': 'chemical'})
            
            # 检查特殊字段
            if txt in special_fields or original_txt in special_fields:
                field_code = special_fields.get(txt) or special_fields.get(original_txt)
                if field_code:
                    special_fields_found.append({'index': i, 'field': field_code, 'type': 'special'})
        
        # 步骤 2: 找出所有数值位置（包含 comparison 信息）
        numbers_pos = []
        for i, text in enumerate(texts):
            val_text = text['text'].strip()
            clean_val = re.sub(r'[≤≥<>=\s\'"]', '', val_text)
            # 匹配：数字、范围、带≤的值
            if re.match(r'^\d+\.?\d*$', clean_val) or ('~' in val_text) or ('≤' in val_text) or ('≥' in val_text):
                if clean_val and clean_val != '0':  # 排除单独的 0
                    # 提取 comparison 信息
                    comparison = None
                    if '≥' in val_text or '不小于' in val_text:
                        comparison = '≥'
                    elif '≤' in val_text or '不大于' in val_text:
                        comparison = '≤'
                    elif '>' in val_text:
                        comparison = '>'
                    elif '<' in val_text:
                        comparison = '<'
                    elif '=' in val_text and '~' not in val_text:
                        comparison = '='
                    
                    numbers_pos.append({'index': i, 'value': val_text, 'clean_value': clean_val, 'comparison': comparison})
        
        # 步骤 3: 为每个元素/字段找最近的数值（在元素后面）
        elements = []
        for elem_info in elements_pos:
            elem_idx = elem_info['index']
            best_match = None
            min_distance = float('inf')
            
            for num_info in numbers_pos:
                num_idx = num_info['index']
                if num_idx > elem_idx:  # 数值必须在元素后面
                    distance = num_idx - elem_idx
                    if distance < min_distance and distance <= 5:  # 限制在 5 个位置内
                        min_distance = distance
                        best_match = num_info
            
            if best_match:
                elements.append({
                    'element': elem_info['element'],
                    'value': best_match['value'],
                    'clean_value': best_match.get('clean_value', best_match['value']),
                    'comparison': best_match.get('comparison'),
                    'type': 'chemical'
                })
        
        # 为特殊字段找数值
        for field_info in special_fields_found:
            field_idx = field_info['index']
            best_match = None
            min_distance = float('inf')
            
            for num_info in numbers_pos:
                num_idx = num_info['index']
                if num_idx > field_idx:
                    distance = num_idx - field_idx
                    if distance < min_distance and distance <= 5:
                        min_distance = distance
                        best_match = num_info
            
            if best_match:
                elements.append({
                    'element': field_info['field'],
                    'value': best_match['value'],
                    'clean_value': best_match.get('clean_value', best_match['value']),
                    'comparison': best_match.get('comparison'),
                    'type': 'special'
                })
        
        logger.info(f"[规则提取] 找到化学元素位置：{len(elements_pos)}个，特殊字段：{len(special_fields_found)}个，数值位置：{len(numbers_pos)}个")
        logger.info(f"[规则提取] 成功匹配：{[(e['element'], e['value'], e['type']) for e in elements]}")
        return {'elements': elements}

    def _format_with_llm(self, extracted_data: Dict, test_category_code: str = None) -> List[Dict]:
        """LLM 只负责格式化和验证，不提取数据"""
        elements = extracted_data.get('elements', [])
        
        if not elements:
            logger.warning("[Hybrid] 没有提取到元素数据")
            return []
        
        # 根据元素类型推断测试类别
        has_special = any(e.get('type') == 'special' for e in elements)
        has_chemical = any(e.get('type') == 'chemical' for e in elements)
        
        # 检查特殊字段来确定类别
        special_fields = [e.get('element') for e in elements if e.get('type') == 'special']
        inferred_category = test_category_code
        if not inferred_category:
            if 'K_IC' in special_fields:
                inferred_category = 'fracture_toughness'
            elif 'A_Ku2' in special_fields or 'impact_energy' in special_fields:
                inferred_category = 'impact'
            elif 'hardness_value' in special_fields or 'hardness_type' in special_fields:
                inferred_category = 'hardness'
            elif 'σ_b' in special_fields or 'σ_0.2' in special_fields:
                inferred_category = 'tension'
            elif has_chemical:
                inferred_category = 'chemical_composition'
        
        # 检查文本中是否包含晶粒度关键词
        text_content = ' '.join([e.get('element', '') for e in elements])
        if '晶粒度' in text_content or '晶粒级别' in text_content or '晶粒尺寸' in text_content:
            inferred_category = 'grain_size'
            logger.info(f"[类别推断] 检测到晶粒度关键词，推断类别为 grain_size")
        
        prompt = f"""你是材料数据格式化专家。将以下已提取的元素 - 数值对转换为数据库规范的 JSON 格式。

已提取的元素数据（包含 comparison 信息）：
{json.dumps(elements, ensure_ascii=False, indent=2)}

推断类别：{inferred_category or test_category_code or 'chemical_composition'}

**重要规则**：
1. 所有元素必须合并到一条数据中
2. 范围值 0.015~0.060 → {{"min_value":"0.015","max_value":"0.060"}}
3. **【必须】小于等于 ≤0.01 → {{"max_value":"0.01","comparison":"≤"}}**
4. **【必须】大于等于 ≥390 → {{"min_value":"390","comparison":"≥"}}**
5. **【关键】如果原始数据中有 comparison 字段（如≥、≤、"不小于"、"不大于"），必须保留并输出**
6. 保留原始精度
7. 单位规则：
   - 化学元素 (C,Cr,Mo 等) 单位为 "%"
   - 拉伸性能 (σ_b,σ_0.2) 单位为 "MPa"
   - 伸长率/断面收缩率 (δ_5,ψ) 单位为 "%"
   - 冲击吸收能量 (A_Ku2) 单位为 "J"
   - 断裂韧度 (K_IC) 单位为 "MPa·m^(-1/2)" 或 "MPa·m⁻¹/²"
8. **【新增字段】item_key**：根据试验条件自动生成项目关键字数组
   - 化学成分：["化学成分"] 或 ["主要元素"]
   - 拉伸高温：["高温", "抗拉"] 或 ["高温", "屈服"]
   - 拉伸室温：["室温", "抗拉"] 或 ["室温", "屈服"]
   - 冲击高温：["高温", "冲击"]
   - 冲击低温：["低温", "冲击"]
   - 持久/蠕变：["持久"] 或 ["蠕变"]
9. **【新增字段】experimental_conditions**：试验条件 JSON
   - 拉伸/冲击高温：{{"temperature": "750℃"}}
   - 拉伸/冲击低温：{{"temperature": "-40℃"}}
   - 持久/蠕变：{{"temperature": "750℃", "stress": "XXX MPa"}}

输出 JSON 格式（包含 item_key 和 experimental_conditions）：
{{"specs":[{{"material_spec_number":"","alloy_grade":"","status":"","specification":"","sampling_direction":"","test_category_code":"{inferred_category or test_category_code or 'chemical_composition'}","test_values":{{"C":{{"item_key":["化学成分"],"experimental_conditions":{{}},"min_value":"0.015","max_value":"0.060","unit":"%"}},"σ_b":{{"item_key":["高温","抗拉"],"experimental_conditions":{{"temperature":"750℃"}},"min_value":"1620","comparison":"≥","unit":"MPa"}}...}},"additional_conditions":{{}},"remarks":""}}]}}

只返回 JSON，不要其他文字。"""

        try:
            llm_start = time.time()
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2048,
                temperature=0,
                timeout=300
            )
            
            llm_elapsed = time.time() - llm_start
            logger.info(f"[性能] LLM 格式化完成，耗时：{llm_elapsed:.2f}秒")
            
            result_text = response.choices[0].message.content
            logger.info(f"[Hybrid] LLM 格式化响应:\n{result_text[:500]}")
            
            return self._extract_json(result_text)
        except Exception as e:
            logger.error(f"[Hybrid] LLM 格式化失败：{e}")
            logger.info("[Hybrid] 使用规则提取的原始数据作为备用")
            return self._fallback_convert(elements, test_category_code)

    def _parse_with_llm(self, recognized_text: str, test_category_code: str = None) -> List[Dict]:
        category_hint = self._get_category_hint(test_category_code)
        
        # JSON 输出格式示例（避免 f-string 嵌套问题）
        json_output_example = '''{"specs":[{"material_spec_number":"xxx","alloy_grade":"xxx","status":"xxx","specification":"xxx","sampling_direction":"xxx","test_category_code":"xxx","test_values":{"field_code":{"item_key":["高温","抗拉"],"experimental_conditions":{"temperature":"704℃"},"min_value":"1620","comparison":">=","unit":"MPa"}},"additional_conditions":{},"remarks":"xxx"}]}'''
        
        prompt = f"""你是材料数据提取专家。从以下 OCR 识别的文本中提取表格数据，转换为符合数据库规范的 JSON 格式。

{category_hint}

**【关键指令 - 必须遵守】**：
0. **首先识别表格中有多少行数据，每行代表一个牌号**
   - 如果表格有 2 行数据（2 个牌号），必须输出 2 条数据
   - 如果表格有 3 行数据（3 个牌号），必须输出 3 条数据
   - 每个牌号必须独立成一条数据
   - **特别注意**：即使多个牌号共享相同的热处理制度/状态，它们仍然是独立的数据行，必须分别输出
1. 同一材料的多个元素/参数必须合并到一条数据中，不要拆分成多条
2. 化学成分表中所有元素 (C,Cr,Mo,Al 等) 都属于同一条材料规范
3. **【强制要求】多牌号识别**：当表格中有多行数据且每行有不同牌号时，必须为每个牌号创建一条独立数据
   - 例如：表格有 "30Si2MnCrMoVE" 和 "31Si2MnCrMoVE" 两个牌号
   - 必须输出 2 条数据，alloy_grade 分别是 "30Si2MnCrMoVE" 和 "31Si2MnCrMoVE"
   - 即使它们的热处理制度相同，也必须分别输出
4. **【强制要求】按测试类别分组**：不同测试类别的性能指标必须拆分到不同的数据记录中
   - 如果一个牌号有 sigma_b, A_Ku2, K_IC 三个不同类别的字段
   - 必须输出 3 条数据：tension(只有sigma_b等), impact(只有A_Ku2), fracture_toughness(只有K_IC)
5. **特殊字段识别**：
   - A_Ku2 或 A_ku2：冲击吸收能量（单位 J），属于冲击类别 (impact)
   - K_IC 或 K_Ic：断裂韧度（单位 MPa·m^(-1/2) 或 MPa·m⁻¹/²），属于断裂韧度类别 (fracture_toughness)
   - sigma_b 或抗拉强度：抗拉强度（单位 MPa），属于拉伸类别 (tension)
   - sigma_0.2 或屈服强度：屈服强度（单位 MPa），属于拉伸类别 (tension)
   - elongation_5d 或断后伸长率(5d)：断后伸长率（长比例试样，单位 %），属于拉伸类别 (tension)
   - elongation_4d 或断后伸长率(4d)：断后伸长率（短比例试样，单位 %），属于拉伸类别 (tension)
   - psi 或断面收缩率：断面收缩率（单位 %），属于拉伸类别 (tension)
   - HRC/HB/HBW/HV/HRA/HRB/HRC等硬度标尺：属于硬度类别 (hardness)
     * 标尺本身填到 test_values.hardness_type（如 "HRC"、"HBW"、"HV"）
     * 数值填到 test_values.hardness_value（带 comparison 和 unit）
     * 例：表格 HRC 列写 "53"，输出 test_values.hardness_type="HRC", test_values.hardness_value={"min_value":"53","comparison":"≥"}
     * 例：表格 HRC 列写 "≥53"，输出 hardness_value={"min_value":"53","comparison":"≥","unit":"HRC"}
6. **宏观组织（低倍）检验特殊处理**：
   - **识别章节结构**：如果文本中有"3.7 低倍"、"3.7.1"、"3.7.2"、"3.7.3"等章节编号，这些都是低倍检验的内容
   - **文字内容合并**：3.7.1、3.7.2 等小节的所有文字描述都属于低倍判定指标
   - **输出格式**：将判定指标描述放到 **test_values.macro_structure_description** 字段中
7. **晶粒度检验特殊处理**：
   - **识别章节结构**：如果文本中有"3.8 晶粒度"等章节编号，这些都是晶粒度检验的内容
   - **输出格式**：将晶粒度要求放到 **test_values.grain_size_description** 字段中

数据库字段要求：
- material_spec_number: 编号，如 "GJB 2351A-2021"，**如果图片中没有明确的标准号，必须设为空字符串**
- alloy_grade: 牌号，如 "30Si2MnCrMoVE"
- status: 状态，如 "T6"、"固溶"、"正火 + 淬火 + 回火"
- specification: 规格，如 "棒材"、"锻件"
- sampling_direction: 取样方向，如 "纵向"、"横向"
- test_category_code: 类别代码，如 "chemical_composition"、"tension"、"impact"、"fracture_toughness"

数值字段规则：
- 范围值 0.015~0.060：min_value="0.015", max_value="0.060"
- **【必须】大于等于 ≥390：min_value="390", comparison=">="**
- **【必须】小于等于 ≤0.01：max_value="0.01", comparison="<="**
- 保留原始精度：0.060 不能写成 0.6

**【新增字段】item_key 和 experimental_conditions**：
- **item_key**：项目关键字数组，用于查询匹配。根据试验条件自动生成
  - 化学成分：["化学成分"]
  - 拉伸高温：["高温", "抗拉"] 或 ["高温", "屈服"]
  - 拉伸室温：["室温", "抗拉"]
  - 冲击高温：["高温", "冲击"]
  - 冲击低温：["低温", "冲击"]
  - 持久/蠕变：["持久"]
- **experimental_conditions**：试验条件 JSON 格式
  - 高温：{"temperature": "704℃"}
  - 低温：{"temperature": "-40℃"}
  - **注意**：试验温度必须从表格标题或文本中提取

OCR 识别的原始文本：
{recognized_text}

请严格按照以下 JSON 格式输出，只返回 JSON，不要其他文字：
{json_output_example}"""

        try:
            llm_start = time.time()
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=3072,
                temperature=0,
                timeout=300
            )
            
            llm_elapsed = time.time() - llm_start
            logger.info(f"[性能] LLM 语义理解完成，耗时：{llm_elapsed:.2f}秒")
            
            result_text = response.choices[0].message.content
            logger.info(f"[Hybrid] LLM 原始响应:\n{result_text}")
            
            return self._extract_json(result_text)
        except Exception as e:
            logger.error(f"[Hybrid] LLM 调用失败：{e}", exc_info=True)
            return []

    def _get_category_hint(self, test_category_code: str = None) -> str:
        if not test_category_code:
            return ""
        
        category_hints = {
            'chemical_composition': '这是化学成分表，包含 C,Cr,Mo,Al,Ti,Co,B,Ni,Si,Mn,S,P,Zr,Cu,Fe 等元素含量',
            'tension': '这是拉伸性能表，包含试验温度、抗拉强度、屈服强度、规定塑性延伸强度、断后伸长率、断面收缩率',
            'impact': '这是冲击性能表，包含试验温度、冲击吸收能量',
            'stress_rupture': '这是持久性能表，包含试验温度、应力、持久时间',
            'creep': '这是蠕变性能表，包含试验温度、应力、蠕变伸长率',
            'hardness': '这是硬度表，包含硬度类型、标尺、硬度值',
            'macro_structure_desctription': '这是宏观组织（低倍）检验表，包含金属流线、缺陷类型、等级、暗斑、白斑、偏析等判定指标要求',
            'macro_structure': '这是宏观组织（低倍）检验表，包含金属流线、缺陷类型、等级、暗斑、白斑、偏析等判定指标要求',
            'macro_structure_description': '这是宏观组织（低倍）检验表，包含金属流线、缺陷类型、等级、暗斑、白斑、偏析等判定指标要求',
            'low_magnification': '这是宏观组织（低倍）检验表，包含金属流线、缺陷类型、等级、暗斑、白斑、偏析等判定指标要求',
            'fracture_inspection': '这是断口检验表',
            'grain_size': '这是晶粒度测定表，包含晶粒度级别、晶粒尺寸等要求，使用 grain_size_description 字段存储描述',
            'non_metallic_inclusion': '这是非金属夹杂物评定表',
            'microstructure': '这是显微组织检验表',
        }
        return category_hints.get(test_category_code, '')

    def _extract_json(self, result_text: str) -> List[Dict]:
        try:
            json_start = result_text.find('{')
            json_end = result_text.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = result_text[json_start:json_end]
                result = json.loads(json_str)
                specs = result.get('specs', [])
                logger.info(f"[Hybrid] 解析得到 {len(specs)} 条数据")
                return specs
        except Exception as e:
            logger.error(f"[Hybrid] 解析 JSON 失败：{e}")
            logger.error(f"[Hybrid] 原始响应：{result_text}")
        return []
    
    def _merge_creep_specs(self, specs: List[Dict]) -> List[Dict]:
        """
        持久试验合并：将同一 material_spec_number 的 stress_rupture 和 tension 数据合并
        
        问题：LLM 经常将持久试验数据拆分成 stress_rupture(sigma, t) 和 tension(test_temperature, delta)
        解决：检测到持久试验特征时，将相关数据合并到 stress_rupture 类别
        
        合并条件：
        1. 相同的 material_spec_number
        2. 一条是 stress_rupture 类别（包含 sigma 或 t 字段）
        3. 另一条是 tension 类别（包含 test_temperature 或 delta 等字段）
        """
        if not specs or len(specs) < 2:
            return specs
        
        # 按 material_spec_number 分组
        grouped = {}
        for spec in specs:
            key = (spec.get('material_spec_number', ''), spec.get('alloy_grade', ''), spec.get('status', ''))
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(spec)
        
        result_specs = []
        merged_count = 0
        
        for key, group in grouped.items():
            # 查找 creep 和 tension 类别
            creep_spec = None
            tension_specs = []
            
            for spec in group:
                category = spec.get('test_category_code', '')
                test_values = spec.get('test_values', {})
                
                # 检查是否是持久试验的 stress_rupture 数据
                if category == 'stress_rupture' and ('sigma' in test_values or 't' in test_values or 'stress' in test_values or 'time' in test_values):
                    creep_spec = spec
                # 检查是否可能是持久试验的 tension 数据（包含温度或延伸率）
                elif category == 'tension' and ('test_temperature' in test_values or 'delta_4' in test_values or 'delta' in test_values):
                    tension_specs.append(spec)
            
            # 如果有 creep 和 tension 数据，合并它们
            if creep_spec and tension_specs:
                print(f"[持久试验] 合并 creep 和 tension 数据：{key}")
                logger.info(f"[持久试验] 合并数据：{key}")
                
                # 合并 test_values
                for tension_spec in tension_specs:
                    for field_name, field_value in tension_spec.get('test_values', {}).items():
                        creep_spec['test_values'][field_name] = field_value
                
                # 合并到 stress_rupture 类别
                creep_spec['test_category_code'] = 'stress_rupture'
                
                # 合并 remarks
                if tension_spec.get('remarks'):
                    if creep_spec.get('remarks'):
                        creep_spec['remarks'] += '；' + tension_spec['remarks']
                    else:
                        creep_spec['remarks'] = tension_spec['remarks']
                
                result_specs.append(creep_spec)
                merged_count += 1
            else:
                # 不需要合并，直接添加
                result_specs.extend(group)
        
        if merged_count > 0:
            print(f"[持久试验] 合并了 {merged_count} 组数据")
            logger.info(f"[持久试验] 合并了 {merged_count} 组数据")
        
        return result_specs
    
    def _process_grain_size_specs(self, specs: List[Dict]) -> List[Dict]:
        """
        晶粒度特殊处理：
        1. 从 grain_size_description 中提取预处理方式 → remarks
        2. 从中提取规格信息（如直径范围）→ specification
        3. 保留晶粒度判定要求 → test_values.grain_size_description
        4. 当描述中包含多个规格时，生成多条记录
        """
        import re
        
        if not specs:
            return specs
        
        result_specs = []
        
        for spec in specs:
            if spec.get('test_category_code') != 'grain_size':
                result_specs.append(spec)
                continue
            
            grain_size_desc = spec.get('test_values', {}).get('grain_size_description', '')
            if not grain_size_desc:
                result_specs.append(spec)
                continue
            
            print(f"[晶粒度] 原始描述：{grain_size_desc}")
            
            preprocessing_patterns = [
                r'晶粒度试样[^。，,]*?(?:加热|保温|冷却)[^。，,]*',
                r'试样[^。，,]*?(?:加热|保温|冷却)[^。，,]*',
                r'加热[到至]?\s*\d+[±±]\s*\d+℃[^。，,]*',
                r'保温\s*\d+\s*min[^。，,]*',
                r'(?:油冷|水冷|空冷)[^。，,]*',
            ]
            
            preprocessing_parts = []
            remaining_desc = grain_size_desc
            
            for pattern in preprocessing_patterns:
                matches = re.findall(pattern, remaining_desc)
                for match in matches:
                    if match not in preprocessing_parts:
                        preprocessing_parts.append(match)
                        remaining_desc = remaining_desc.replace(match, '', 1)
            
            preprocessing_text = '，'.join(preprocessing_parts)
            
            spec_patterns = [
                r'直径\s*(?:不大于|大于|≤|>)\s*\d+\s*mm\s*(?:的|之)?.*?锻件',
                r'规格[：:][^。，,]+',
            ]
            
            spec_parts = []
            for pattern in spec_patterns:
                matches = re.findall(pattern, remaining_desc)
                for match in matches:
                    if match not in spec_parts:
                        spec_parts.append(match)
                        remaining_desc = remaining_desc.replace(match, '', 1)
            
            spec_text = '，'.join(spec_parts) if spec_parts else ''
            
            requirement_text = remaining_desc.strip('，。、, ')
            
            print(f"[晶粒度] 预处理：{preprocessing_text}")
            print(f"[晶粒度] 规格：{spec_text}")
            print(f"[晶粒度] 判定要求：{requirement_text}")
            
            if spec_parts:
                combined_desc = grain_size_desc
                spec_req_list = []
                
                last_pos = 0
                sorted_specs = sorted(spec_parts, key=lambda x: combined_desc.find(x) if x in combined_desc else 999)
                
                for i, spec_part in enumerate(sorted_specs):
                    spec_start = combined_desc.find(spec_part, last_pos)
                    if spec_start == -1:
                        continue
                    
                    search_start = spec_start + len(spec_part)
                    if i + 1 < len(sorted_specs):
                        next_spec_start = combined_desc.find(sorted_specs[i + 1], search_start)
                        if next_spec_start == -1:
                            next_spec_start = len(combined_desc)
                        segment = combined_desc[search_start:next_spec_start]
                    else:
                        segment = combined_desc[search_start:]
                    
                    req_match = re.search(r'晶粒度级别.{0,20}', segment)
                    if req_match:
                        spec_req_list.append((spec_part, req_match.group().strip()))
                    else:
                        req_match = re.search(r'晶粒度.{0,20}', segment)
                        if req_match:
                            spec_req_list.append((spec_part, req_match.group().strip()))
                        else:
                            spec_req_list.append((spec_part, requirement_text))
                    
                    last_pos = spec_start + len(spec_part)
                
                for spec_part, req_text in spec_req_list:
                    new_spec = spec.copy()
                    new_spec['test_values'] = spec.get('test_values', {}).copy()
                    new_spec['test_values']['grain_size_description'] = req_text
                    
                    new_spec['specification'] = spec_part.strip('，。、, ')
                    new_spec['remarks'] = preprocessing_text.strip('，。、, ')
                    
                    result_specs.append(new_spec)
                    print(f"[晶粒度] 生成记录：规格={new_spec['specification']}, 要求={new_spec['test_values']['grain_size_description']}")
            else:
                new_spec = spec.copy()
                new_spec['test_values'] = spec.get('test_values', {}).copy()
                new_spec['test_values']['grain_size_description'] = requirement_text
                new_spec['specification'] = spec.get('specification', '-') or '-'
                new_spec['remarks'] = preprocessing_text.strip('，。、, ') if preprocessing_text else spec.get('remarks', '')
                result_specs.append(new_spec)

        return result_specs

    def _split_text_field_specs(self, specs: List[Dict]) -> List[Dict]:
        """
        **兜底拆分**：对 grain_size_description / macro_structure_description 等 text 字段
        检测 value 字段中是否包含多个"直径"规格，若是则拆成多条记录。

        场景：LLM 把多个规格合并到 1 条数据的 grain_size_description 字段中：
          "直径不大于 300mm 的棒材晶粒度级别大于等于 7 级，直径大于 300mm 的棒材晶粒度级别大于等于 6 级"
        期望：拆成 2 条数据，每条对应一个规格。
        """
        import re

        if not specs:
            return specs

        # 适用的 text 字段及对应规格匹配模式
        text_field_spec = {
            'grain_size_description': {
                'spec_patterns': [
                    r'直径\s*(?:不大于|大于|≤|≥|<|>|等于)\s*\d+\s*mm[^,。；;;]*?(?=晶粒度|，|$)',
                    r'直径\s*\d+\s*mm[^,。；;;]*?(?=晶粒度|，|$)',
                ],
                'req_patterns': [
                    r'晶粒度级别[^,。；;;]*',
                    r'晶粒度[^,。；;;]*?(?:\d+\s*级[^,。；;;]*)?',
                ],
            },
        }

        result_specs = []

        for spec in specs:
            test_values = spec.get('test_values', {})
            if not isinstance(test_values, dict):
                result_specs.append(spec)
                continue

            # 检查是否有需要拆分的 text 字段
            target_field = None
            field_conf = None
            for tf, conf in text_field_spec.items():
                if tf in test_values:
                    target_field = tf
                    field_conf = conf
                    break

            if not target_field:
                result_specs.append(spec)
                continue

            field_data = test_values[target_field]
            # 兼容字符串格式：LLM 直接把字符串放到 grain_size_description 字段
            if isinstance(field_data, str):
                value_text = field_data
                field_data = {'value': field_data}
            elif isinstance(field_data, dict):
                value_text = field_data.get('value', '')
            else:
                result_specs.append(spec)
                continue

            if not value_text or not isinstance(value_text, str):
                result_specs.append(spec)
                continue

            # 找所有"直径"开头的规格段
            spec_parts = []
            for pattern in field_conf['spec_patterns']:
                matches = re.findall(pattern, value_text)
                for m in matches:
                    cleaned = m.strip('，。、, ')
                    if cleaned and cleaned not in spec_parts:
                        spec_parts.append(cleaned)

            if len(spec_parts) < 2:
                # 只有一个规格，无需拆分
                result_specs.append(spec)
                continue

            print(f"[text字段拆分] {target_field}: 检测到 {len(spec_parts)} 个规格 → 拆分")

            # 按规格位置分段提取每段的判定要求
            positions = []
            for sp in spec_parts:
                pos = value_text.find(sp)
                if pos >= 0:
                    positions.append((pos, sp))
            positions.sort()

            for i, (pos, sp) in enumerate(positions):
                spec_end = pos + len(sp)
                if i + 1 < len(positions):
                    next_pos = positions[i + 1][0]
                    segment = value_text[spec_end:next_pos]
                else:
                    segment = value_text[spec_end:]

                # 提取判定要求
                req_text = segment.strip('，。、, ')
                for rp in field_conf['req_patterns']:
                    rm = re.search(rp, segment)
                    if rm:
                        req_text = rm.group().strip('，。、, ')
                        break

                # 生成新记录（保持原始 field_data 格式：对象或字符串）
                new_spec = spec.copy()
                new_spec['test_values'] = test_values.copy()
                if isinstance(test_values.get(target_field), str):
                    # LLM 输出是字符串格式：直接赋值字符串
                    new_spec['test_values'][target_field] = req_text
                else:
                    # 对象格式：复制原对象并更新 value 字段
                    new_field_data = field_data.copy()
                    new_field_data['value'] = req_text
                    new_spec['test_values'][target_field] = new_field_data
                new_spec['specification'] = sp
                result_specs.append(new_spec)
                print(f"[text字段拆分]   规格={sp} → 判定={req_text}")

        return result_specs

    def _split_specs_by_category(self, specs: List[Dict]) -> List[Dict]:
        """
        **关键优化**：按测试类别强制拆分数据
        
        问题：LLM 经常将 A_Ku2 和 K_IC 错误地放在 tension 类别中
        解决：根据字段内容，将每条数据按测试类别拆分成多条
        
        字段分类规则：
        - tension: sigma_b, sigma_0.2, delta_5, psi, yield_strength, tensile_strength, elongation, reduction_of_area
        - impact: A_Ku2, A_ku2, impact_energy, a_ku2
        - fracture_toughness: K_IC, K_Ic, k_ic, fracture_toughness
        - chemical_composition: C, Cr, Mo, Al, Ti, Co, B, Ni, Si, Mn, S, P, Zr, Cu, Fe, 等元素
        """
        if not specs:
            return []
        
        # 字段到测试类别的映射（大小写不敏感，包含 Unicode 字符）
        field_category_map = {
            # 拉伸性能 - ASCII 版本
            'sigma_b': 'tension', 'SIGMA_B': 'tension', 'Σb': 'tension', 'σb': 'tension',
            'sigma_0.2': 'tension', 'SIGMA_0.2': 'tension', 'Σ0.2': 'tension', 'σ0.2': 'tension',
            'σ_b': 'tension', 'σ_0.2': 'tension',  # Unicode 版本
            'delta_5': 'tension', 'DELTA_5': 'tension', 'Δ5': 'tension', 'δ5': 'tension',
            'δ_5': 'tension',  # Unicode 版本
            'delta_4': 'tension', 'DELTA_4': 'tension', 'Δ4': 'tension', 'δ4': 'tension',
            'δ_4': 'tension',  # δ₄短比例试样
            'delta_10': 'tension', 'DELTA_10': 'tension', 'Δ10': 'tension', 'δ10': 'tension',
            'δ_10': 'tension',  # δ₁₀超长比例试样
            'delta_11': 'tension', 'DELTA_11': 'tension', 'Δ11': 'tension', 'δ11': 'tension',
            'δ_11': 'tension',  # δ₁₁特殊比例试样
            'delta': 'tension', 'DELTA': 'tension', 'Δ': 'tension', 'δ': 'tension',  # 通用延伸率
            # 断后伸长率 elongation 系列 (统一归类到 tension)
            'elongation': 'tension', 'elong': 'tension',  # 无后缀
            'elongation_4d': 'tension', 'elong_4d': 'tension', 'elongation_4D': 'tension',  # 4d 后缀
            'elongation_5d': 'tension', 'elong_5d': 'tension', 'elongation_5D': 'tension',  # 5d 后缀
            'elongation_10d': 'tension', 'elong_10d': 'tension', 'elongation_10D': 'tension',  # 10d 后缀
            'elongation_11d': 'tension', 'elong_11d': 'tension', 'elongation_11D': 'tension',  # 11d 后缀
            'sigma': 'stress_rupture', 'stress': 'stress_rupture',  # 应力
            't': 'stress_rupture', 'time': 'stress_rupture', 'duration': 'stress_rupture',  # 持久时间
            'delta_creep': 'stress_rupture', 'creep_elongation': 'stress_rupture',  # 蠕变伸长率
            'psi_creep': 'stress_rupture', 'creep_reduction': 'stress_rupture',  # 蠕变断面收缩率
            'test_temperature': 'tension', 'TEST_TEMPERATURE': 'tension', 'temperature': 'tension',  # 试验温度（默认属于拉伸）
            'psi': 'tension', 'PSI': 'tension', 'Ψ': 'tension', 'ψ': 'tension',  # 包含 Unicode
            'yield_strength': 'tension', 'yield': 'tension',
            'tensile_strength': 'tension', 'tensile': 'tension',
            'elongation': 'tension', 'elong': 'tension',
            'reduction_of_area': 'tension', 'reduction': 'tension',
            'upper_yield_strength': 'tension',
            'lower_yield_strength': 'tension',
            'proof_strength': 'tension', 'proof': 'tension',
            
            # 硬度性能
            'HRC': 'hardness', 'hrc': 'hardness', 'Hrc': 'hardness',
            'HB': 'hardness', 'hb': 'hardness', 'HBW': 'hardness', 'hbw': 'hardness',
            'HV': 'hardness', 'hv': 'hardness', 'HV10': 'hardness', 'HV30': 'hardness',
            'HRA': 'hardness', 'hra': 'hardness',
            'HRB': 'hardness', 'hrb': 'hardness',
            'HRD': 'hardness', 'hrd': 'hardness',
            'HRE': 'hardness', 'hre': 'hardness',
            'HRF': 'hardness', 'hrf': 'hardness',
            'HRG': 'hardness', 'hrg': 'hardness',
            'HRP': 'hardness', 'hrp': 'hardness',
            'HRS': 'hardness', 'hrs': 'hardness',
            'HRV': 'hardness', 'hrv': 'hardness',
            'hardness': 'hardness', 'HARDNESS': 'hardness',
            'hardness_value': 'hardness',
            'hardness_type': 'hardness',
            'scale': 'hardness',
            
            # 宏观组织/低倍检验
            'low_magnification': 'macro_structure',
            'low_mag': 'macro_structure',
            'macro_structure': 'macro_structure',
            'macro_structure_desctription': 'macro_structure',
            'macro_structure_description': 'macro_structure',
            'defect_type': 'macro_structure',
            'defect': 'macro_structure',
            'metal_flow': 'macro_structure',
            'metal_line': 'macro_structure',
            'flow_line': 'macro_structure',
            'macro_result': 'macro_structure',
            'low_times_result': 'macro_structure',
            'low_times': 'macro_structure',
            'metal_flow_direction': 'macro_structure',
            'defect_requirement': 'macro_structure',
            'dark_spot': 'macro_structure',
            'white_spot': 'macro_structure',
            'radial_segregation': 'macro_structure',
            'ring_pattern': 'macro_structure',
            
            # 冲击性能
            'A_Ku2': 'impact', 'A_ku2': 'impact', 'a_ku2': 'impact', 'AKU2': 'impact',
            'A_KU2': 'impact', 'A_kv2': 'impact', 'AKV2': 'impact',
            'impact_energy': 'impact', 'impact': 'impact',
            'ku2': 'impact', 'KU2': 'impact',
            
            # 断裂韧度
            'K_IC': 'fracture_toughness', 'K_Ic': 'fracture_toughness', 'k_ic': 'fracture_toughness',
            'KIC': 'fracture_toughness', 'K1C': 'fracture_toughness',
            'K I C': 'fracture_toughness', 'K IC': 'fracture_toughness',
            'kic': 'fracture_toughness', 'k1c': 'fracture_toughness',
            'fracture_toughness': 'fracture_toughness', 'fracture': 'fracture_toughness',
            
            # 化学成分（常见元素）
            'C': 'chemical_composition', 'c': 'chemical_composition',
            'Cr': 'chemical_composition', 'cr': 'chemical_composition',
            'Mo': 'chemical_composition', 'mo': 'chemical_composition',
            'Al': 'chemical_composition', 'al': 'chemical_composition',
            'Ti': 'chemical_composition', 'ti': 'chemical_composition',
            'Co': 'chemical_composition', 'co': 'chemical_composition',
            'B': 'chemical_composition', 'b': 'chemical_composition',
            'Ni': 'chemical_composition', 'ni': 'chemical_composition',
            'Si': 'chemical_composition', 'si': 'chemical_composition',
            'Mn': 'chemical_composition', 'mn': 'chemical_composition',
            'S': 'chemical_composition', 's': 'chemical_composition',
            'P': 'chemical_composition', 'p': 'chemical_composition',
            'Zr': 'chemical_composition', 'zr': 'chemical_composition',
            'Cu': 'chemical_composition', 'cu': 'chemical_composition',
            'Fe': 'chemical_composition', 'fe': 'chemical_composition',
            'Pb': 'chemical_composition', 'pb': 'chemical_composition',
            'As': 'chemical_composition', 'as_': 'chemical_composition',
            'Sn': 'chemical_composition', 'sn': 'chemical_composition',
            'Sb': 'chemical_composition', 'sb': 'chemical_composition',
            'Bi': 'chemical_composition', 'bi': 'chemical_composition',
            'Ag': 'chemical_composition', 'ag': 'chemical_composition',
            'V': 'chemical_composition', 'v': 'chemical_composition',
            'W': 'chemical_composition', 'w': 'chemical_composition',
            'Mg': 'chemical_composition', 'mg': 'chemical_composition',
            'Nb': 'chemical_composition', 'nb': 'chemical_composition',
        }
        
        result_specs = []

        # 硬度标尺字段名映射：把 HRC/HB/HV/HRB 等统一映射为 hardness_value
        hardness_scale_map = {
            'HRC': 'hardness_value', 'hrc': 'hardness_value', 'Hrc': 'hardness_value',
            'HB': 'hardness_value', 'hb': 'hardness_value', 'HBW': 'hardness_value', 'hbw': 'hardness_value',
            'HV': 'hardness_value', 'hv': 'hardness_value', 'HV1': 'hardness_value', 'HV5': 'hardness_value',
            'HV10': 'hardness_value', 'HV30': 'hardness_value', 'HV50': 'hardness_value',
            'HRA': 'hardness_value', 'hra': 'hardness_value',
            'HRB': 'hardness_value', 'hrb': 'hardness_value',
            'HRD': 'hardness_value', 'hrd': 'hardness_value',
            'HRE': 'hardness_value', 'hre': 'hardness_value',
            'HRF': 'hardness_value', 'hrf': 'hardness_value',
            'HRG': 'hardness_value', 'hrg': 'hardness_value',
            'HR15N': 'hardness_value', 'HR30N': 'hardness_value', 'HR45N': 'hardness_value',
            '硬度': 'hardness_value', '硬度值': 'hardness_value', 'HRC硬度': 'hardness_value',
        }

        for spec in specs:
            test_values = spec.get('test_values', {})
            if not test_values:
                result_specs.append(spec)
                continue

            # **保留原始类别**：如果 spec 已经被 LLM 标记为 creep，则优先保留在 creep 类别
            # 防止 stress/time 等字段被错误地归类到 stress_rupture
            original_category = spec.get('test_category_code', 'tension')

            # 按类别分组字段
            category_groups = {}
            for field_name, field_value in test_values.items():
                # 标准化字段名（转小写后查找）
                field_name_lower = field_name.lower()
                field_name_upper = field_name.upper()

                # 查找字段对应的类别（尝试多种匹配方式）
                category = field_category_map.get(field_name) or \
                           field_category_map.get(field_name_lower) or \
                           field_category_map.get(field_name_upper) or \
                           spec.get('test_category_code', 'tension')

                # **修复**：如果原始类别是 creep，且字段是 stress/time/duration 等共有的字段，
                # 不要强行归到 stress_rupture，而是保留在 creep
                if original_category == 'creep' and category == 'stress_rupture':
                    if field_name in ('stress', 'test_temperature', 'temperature', 'time', 't', 'duration',
                                       'creep_elongation_4d', 'creep_elongation_5d', 'creep_reduction_of_area',
                                       'residual_deformation', 'rupture_time', 'test_time'):
                        category = 'creep'

                # **硬度标尺字段名规范化**：把 HRC/HB/HV/HRB 等改为 hardness_value，并把标尺名存到 unit 字段
                normalized_field_name = field_name
                if category == 'hardness' and field_name in hardness_scale_map:
                    normalized_field_name = 'hardness_value'
                    if isinstance(field_value, dict):
                        # 把标尺名（如 HRC）存到 unit 字段（若 unit 字段已存在则保留原值）
                        if 'unit' not in field_value or not field_value.get('unit'):
                            field_value = {**field_value, 'unit': field_name}
                        # 同步把标尺记录到 hardness_type（若 hardness_type 字段不存在）
                    logger.info(f"[硬度规范化] 字段 '{field_name}' -> hardness_value, 标尺={field_name}")

                # 持久试验特殊处理：如果数据包含持久试验特征字段（sigma, t），则将相关字段都归为 stress_rupture 类别
                has_creep_fields = any(
                    f in ['sigma', 'stress', 't', 'time', 'duration']
                    for f in test_values.keys()
                )
                if has_creep_fields:
                    if field_name in ['test_temperature', 'delta_4', 'delta', 'elongation', 'psi', 'reduction_of_area']:
                        category = 'stress_rupture'
                        logger.info(f"[持久试验] 字段 '{field_name}' 归为 stress_rupture 类别")

                if category not in category_groups:
                    category_groups[category] = {}
                category_groups[category][normalized_field_name] = field_value
                logger.info(f"[拆分匹配] 字段 '{field_name}' -> 类别 '{category}'")

            # **硬度类别后处理**：把硬度标尺名提取到 hardness_type 字段
            if 'hardness' in category_groups:
                hardness_fields = category_groups['hardness']
                # 找出 unit 字段中的标尺名
                hardness_type_value = None
                for fk, fv in list(hardness_fields.items()):
                    if isinstance(fv, dict) and fv.get('unit') and fk == 'hardness_value':
                        # 标尺名（如 HRC）可能就在 unit 字段里
                        unit_val = fv.get('unit', '')
                        if unit_val in ['HRC', 'HB', 'HBW', 'HV', 'HRA', 'HRB', 'HRD', 'HRE', 'HRF', 'HRG',
                                        'HR15N', 'HR30N', 'HR45N', 'HV1', 'HV5', 'HV10', 'HV30', 'HV50',
                                        'HRC硬度', '硬度', '硬度值']:
                            hardness_type_value = unit_val
                            # 把 unit 字段清空（标尺不算单位）或保留为标尺
                            # 这里保留标尺在 unit 中，同时写入 hardness_type
                            break
                # 如果找到了 hardness_type 但没在 hardness_type 字段里，则补充
                if hardness_type_value and 'hardness_type' not in hardness_fields:
                    hardness_fields['hardness_type'] = hardness_type_value
                    logger.info(f"[硬度规范化] 补充 hardness_type={hardness_type_value}")
            
            # 为每个类别创建一条数据
            original_category = spec.get('test_category_code', 'tension')
            for category, fields in category_groups.items():
                # 自动生成 item_key 和 experimental_conditions
                processed_fields = self._process_item_key_and_conditions(fields, category)
                
                new_spec = {
                    'material_spec_number': spec.get('material_spec_number', ''),
                    'alloy_grade': spec.get('alloy_grade', ''),
                    'status': spec.get('status', ''),
                    'specification': spec.get('specification', '-'),
                    'sampling_direction': spec.get('sampling_direction', '-'),
                    'test_category_code': category,
                    'test_values': processed_fields,
                    'additional_conditions': spec.get('additional_conditions', {}),
                    'remarks': spec.get('remarks', '')
                }
                result_specs.append(new_spec)
                logger.info(f"[拆分] 牌号{spec.get('alloy_grade', '')}: {category} 类别包含 {len(fields)} 个字段 → {list(fields.keys())}")
        
        logger.info(f"[拆分] 原始 {len(specs)} 条数据 → 拆分后 {len(result_specs)} 条数据")
        return result_specs
    
    def _process_item_key_and_conditions(self, fields: Dict, category: str) -> Dict:
        """
        处理 item_key 和 experimental_conditions
        如果字段数据中已有 item_key 和 experimental_conditions，保持不变
        如果没有，自动生成
        """
        import re

        # 提取温度信息
        temperature = None
        test_temperature = None
        for field_name, field_data in fields.items():
            if not isinstance(field_data, dict):
                continue
            # 从 test_temperature 字段提取温度
            if field_name in ['test_temperature', 'temperature'] and 'value' in field_data:
                temp_val = str(field_data.get('value', '')).strip()
                if '℃' in temp_val or '°C' in temp_val:
                    temperature = temp_val
                    test_temperature = temp_val
                elif '室温' in temp_val or '常温' in temp_val:
                    temperature = '室温'
                    test_temperature = '室温'
                elif '低温' in temp_val:
                    temperature = temp_val
                    test_temperature = temp_val
                elif re.match(r'^-?\d+(\.\d+)?$', temp_val):
                    # 纯数字（如 "650"、"650.5"）→ 视为 "650℃"
                    if float(temp_val) < 0:
                        # 负数视为低温（如 -40℃）
                        temperature = f'{temp_val}℃'
                        test_temperature = f'{temp_val}℃'
                    else:
                        temperature = f'{temp_val}℃'
                        test_temperature = f'{temp_val}℃'
            # 从 experimental_conditions 中提取温度
            exp_cond = field_data.get('experimental_conditions', {})
            if isinstance(exp_cond, dict) and exp_cond.get('temperature'):
                # **优先使用字段已设置的温度**（避免后续被 室温 覆盖）
                temperature = exp_cond.get('temperature')

        # 确定温度类型
        temp_type = None
        if temperature:
            if '室温' in str(temperature) or '常温' in str(temperature):
                temp_type = '室温'
            elif '低' in str(temperature):
                temp_type = '低温'
            elif '℃' in str(temperature) or '°C' in str(temperature):
                temp_type = '高温'

        # 为每个字段处理 item_key 和 experimental_conditions
        result = {}
        for field_name, field_data in fields.items():
            if not isinstance(field_data, dict):
                result[field_name] = field_data
                continue

            new_field_data = field_data.copy()

            # 处理 experimental_conditions（先于温度填充，确保已存在的值不被覆盖）
            if 'experimental_conditions' not in new_field_data:
                new_field_data['experimental_conditions'] = {}
            if not isinstance(new_field_data['experimental_conditions'], dict):
                new_field_data['experimental_conditions'] = {}

            # 如果有温度信息且当前字段没有温度，则填充
            if temperature and not new_field_data['experimental_conditions'].get('temperature'):
                new_field_data['experimental_conditions']['temperature'] = temperature

            # 处理 item_key
            if 'item_key' not in new_field_data or not new_field_data['item_key']:
                item_key = self._generate_item_key(field_name, category, temp_type)
                new_field_data['item_key'] = item_key

            result[field_name] = new_field_data

        return result
    
    def _generate_item_key(self, field_name: str, category: str, temp_type: str) -> list:
        """根据字段名、类别和温度类型生成 item_key"""
        field_lower = field_name.lower()
        
        # 化学成分
        if category == 'chemical_composition':
            return ['化学成分']
        
        # 温度关键字
        temp_keywords = []
        if temp_type == '高温':
            temp_keywords = ['高温']
        elif temp_type == '低温':
            temp_keywords = ['低温']
        elif temp_type == '室温':
            temp_keywords = ['室温']
        
        # 根据字段类型生成关键字
        field_keywords = []
        
        # 拉伸性能
        if category == 'tension':
            if any(f in field_lower for f in ['sigma_b', 'tensile', '抗拉', 'rm']):
                field_keywords = ['抗拉']
            elif any(f in field_lower for f in ['sigma_0.2', 'sigma_0', 'yield', '屈服', 'rp']):
                field_keywords = ['屈服']
            elif any(f in field_lower for f in ['elongation', 'delta', '伸长', 'elong']):
                field_keywords = ['伸长']
            elif any(f in field_lower for f in ['psi', 'reduction', '断面收缩', 'z']):
                field_keywords = ['收缩']
            else:
                field_keywords = []
        
        # 冲击性能
        elif category == 'impact':
            field_keywords = ['冲击']
        
        # 持久/蠕变
        elif category in ['stress_rupture', 'creep']:
            field_keywords = ['持久']
        
        # 断裂韧度
        elif category == 'fracture_toughness':
            field_keywords = ['断裂韧度']
        
        # 硬度
        elif category == 'hardness':
            field_keywords = ['硬度']
        
        # 宏观组织
        elif category == 'macro_structure':
            field_keywords = ['低倍']
        
        # 晶粒度
        elif category == 'grain_size':
            field_keywords = ['晶粒度']
        
        # 合并关键字
        return temp_keywords + field_keywords if temp_keywords else field_keywords

    def _fallback_convert(self, elements: List[Dict], test_category_code: str = None) -> List[Dict]:
        """备用转换函数：当 LLM 失败时，直接将规则提取的元素转换为规格数据"""
        import re
        
        test_values = {}
        for item in elements:
            elem = item.get('element', '')
            value = item.get('value', '')
            comparison = item.get('comparison')  # 获取 comparison 信息
            clean_value = item.get('clean_value', value)
            
            if not elem or not value:
                continue
            
            value = value.strip()
            clean_value = re.sub(r'[≤≥<>=\s\'"]', '', value) if not clean_value else clean_value
            
            if not re.match(r'^\d+\.?\d*$', clean_value):
                logger.warning(f"[备用] 跳过无效值：{elem}={value}")
                continue
            
            if '~' in value or '-' in value:
                parts = re.split(r'[~\-]', value)
                if len(parts) >= 2:
                    test_values[elem] = {
                        "min_value": parts[0],
                        "max_value": parts[1],
                        "unit": "%"
                    }
            elif comparison:  # 如果有 comparison 信息，使用它
                if comparison in ['≥', '>']:
                    test_values[elem] = {
                        "min_value": clean_value,
                        "comparison": comparison,
                        "unit": "%"
                    }
                elif comparison in ['≤', '<']:
                    test_values[elem] = {
                        "max_value": clean_value,
                        "comparison": comparison,
                        "unit": "%"
                    }
                elif comparison == '=':
                    test_values[elem] = {
                        "value": clean_value,
                        "comparison": comparison,
                        "unit": "%"
                    }
            else:
                test_values[elem] = {
                    "value": clean_value,
                    "unit": "%"
                }
        
        if test_values:
            spec = {
                "material_spec_number": "",
                "alloy_grade": "",
                "status": "",
                "specification": "",
                "sampling_direction": "",
                "test_category_code": test_category_code or "chemical_composition",
                "test_values": test_values,
                "additional_conditions": {},
                "remarks": ""
            }
            logger.info(f"[Hybrid] 备用转换成功，得到 {len(test_values)} 个元素")
            return [spec]
        else:
            logger.warning("[Hybrid] 备用转换失败，没有有效的元素数据")
            return []
