import base64
import io
import json
import time
import logging
from PIL import Image
from typing import List, Dict
from openai import OpenAI

logger = logging.getLogger(__name__)

class VisionMaterialParser:
    def __init__(self, api_key: str, base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1", model: str = "qwen-vl-max"):
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        logger.info(f"[初始化] VisionMaterialParser 初始化完成，模型: {model}")

    def parse_image_from_base64(self, base64_data: str, test_category_code: str = None) -> List[Dict]:
        start_time = time.time()
        
        if ',' in base64_data:
            base64_data = base64_data.split(',')[1]

        try:
            image_data = base64.b64decode(base64_data)
            image = Image.open(io.BytesIO(image_data))
            
            image_base64 = base64.b64encode(image_data).decode('utf-8')
            image_mime = 'jpeg'
            if image.format == 'PNG':
                image_mime = 'png'
            elif image.format == 'WEBP':
                image_mime = 'webp'
            
            data_url = f"data:image/{image_mime};base64,{image_base64}"
            
            logger.info(f"[Vision] 开始视觉识别...")
            
            prompt = self._build_prompt(test_category_code)
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": data_url
                                }
                            },
                            {
                                "type": "text",
                                "text": prompt
                            }
                        ]
                    }
                ],
                max_tokens=4096,
                temperature=0,
                timeout=300
            )
            
            result_text = response.choices[0].message.content
            elapsed = time.time() - start_time
            logger.info(f"[性能] 视觉识别完成，耗时：{elapsed:.2f}秒")
            logger.info(f"[Vision] 原始响应:\n{result_text[:500]}...")
            
            specs = self._extract_json(result_text)
            
            for spec in specs:
                if not spec.get('material_spec_number'):
                    spec['material_spec_number'] = '-'
                if not spec.get('alloy_grade'):
                    spec['alloy_grade'] = '-'
                if not spec.get('status'):
                    spec['status'] = '-'
                if not spec.get('specification'):
                    spec['specification'] = '-'
                if not spec.get('sampling_direction'):
                    spec['sampling_direction'] = '-'
            
            specs = self._infer_comparison(specs)
            
            return specs
            
        except Exception as e:
            logger.error(f"[Vision] 识别失败：{e}", exc_info=True)
            return []

    def _load_prompt_template(self, test_category_code: str = None) -> str:
        """从数据库加载指定类别的提示词模板"""
        if not test_category_code:
            return None
        
        try:
            import os
            db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'material_spec.db')
            if not os.path.exists(db_path):
                return None
            
            from database.operations import MaterialDatabase
            db = MaterialDatabase('material_spec.db')
            
            prompts = db.get_prompt_templates(category_code=test_category_code, active_only=True)
            default_prompt = next((p for p in prompts if p.get('is_default')), None)
            
            if default_prompt:
                logger.info(f"[提示词] 使用 {test_category_code} 的默认提示词：{default_prompt['name']}")
                return default_prompt['prompt_text']
            
            if prompts:
                logger.info(f"[提示词] 使用 {test_category_code} 的提示词：{prompts[0]['name']}")
                return prompts[0]['prompt_text']
            
            logger.info(f"[提示词] 未找到 {test_category_code} 的提示词模板")
            return None
        except Exception as e:
            logger.warning(f"[提示词] 加载失败：{e}")
            return None

    def _build_prompt(self, test_category_code: str = None) -> str:
        db_prompt = self._load_prompt_template(test_category_code)
        if db_prompt:
            return db_prompt
        
        category_hint = ""
        if test_category_code:
            category_hints = {
                'chemical_composition': '这是化学成分表，包含 C,Cr,Mo,Al,Ti,Co,B,Ni,Si,Mn,S,P,Zr,Cu,Fe,Mg 等元素含量',
                'tension': '这是拉伸性能表，包含试验温度、抗拉强度、屈服强度、断后伸长率',
                'impact': '这是冲击性能表，包含试验温度、冲击吸收能量',
                'hardness': '这是硬度表',
                'macro_structure_desctription': '这是宏观组织（低倍）检验表，包含金属流线方向、缺陷类型、等级要求等文字描述',
                'macro_structure': '这是宏观组织（低倍）检验表，包含金属流线方向、缺陷类型、等级要求等文字描述',
                'macro_structure_description': '这是宏观组织（低倍）检验表，包含金属流线方向、缺陷类型、等级要求等文字描述',
                'low_magnification': '这是宏观组织（低倍）检验表，包含金属流线方向、缺陷类型、等级要求等文字描述',
                'grain_size': '这是晶粒度测定表，包含晶粒度级别、晶粒尺寸等要求，使用 grain_size_description 字段存储描述',
            }
            category_hint = category_hints.get(test_category_code, '')
        
        # JSON 输出格式示例
        json_output_example = '{"specs":[{"material_spec_number":"xxx","alloy_grade":"xxx","status":"xxx","specification":"xxx","sampling_direction":"xxx","test_category_code":"xxx","test_values":{"field_code":{"item_key":["高温","抗拉"],"experimental_conditions":{"temperature":"704℃"},"min_value":"1620","comparison":">=","unit":"MPa"}},"additional_conditions":{},"remarks":"xxx"}]}'
        
        prompt = """你是材料数据提取专家。从以下图片中提取表格数据，转换为符合数据库规范的 JSON 格式。

""" + category_hint + """

**【关键指令 - 必须遵守】**：
0. **首先识别表格中有多少行数据，每行代表一个牌号**
   - 如果表格有 2 行数据（2 个牌号），必须输出 2 条数据
   - 如果表格有 3 行数据（3 个牌号），必须输出 3 条数据
   - 每个牌号必须独立成一条数据
   - **特别注意**：即使多个牌号共享相同的热处理制度/状态，它们仍然是独立的数据行，必须分别输出
1. 同一材料的多个元素/参数必须合并到一条数据中，不要拆分成多条
2. 化学成分表中所有元素都属于同一条材料规范
3. **【强制要求】按测试类别分组**：不同测试类别的性能指标必须拆分到不同的数据记录中
   - 如果一个牌号有 σ_b, A_Ku2, K_IC 三个不同类别的字段
   - 必须输出 3 条数据：tension(只有σ_b等), impact(只有A_Ku2), fracture_toughness(只有K_IC)
4. **特殊字段识别**：
   - A_Ku2 或 A_ku2：冲击吸收能量（单位 J），属于冲击类别 (impact)
   - K_IC 或 K_Ic：断裂韧度（单位 MPa·m^(-1/2) 或 MPa·m⁻¹/²），属于断裂韧度类别 (fracture_toughness)
   - σ_b 或 sigma_b：抗拉强度（单位 MPa），属于拉伸类别 (tension)
   - σ_0.2 或 sigma_0.2：屈服强度（单位 MPa），属于拉伸类别 (tension)
   - 断后伸长率（单位 %）：统一输出为 elongation 系列字段名
     * 断后伸长率、断后伸长率A、δ、delta、elongation：无后缀 → "elongation"
     * **δ₄ 或 delta_4**：短比例试样（L₀=4d₀）→ "elongation_4d"
     * **δ₅ 或 delta_5**：长比例试样（L₀=5d₀）→ "elongation_5d"
     * δ₁₀ 或 delta_10：超长比例试样（L₀=10d₀）→ "elongation_10d"
     * δ₁₁ 或 delta_11：特殊比例试样 → "elongation_11d"
   - ψ 或 psi：断面收缩率（单位 %），属于拉伸类别 (tension)
   - **持久/蠕变性能**：
     * σ 或 sigma：应力（单位 MPa），属于持久类别 (stress_rupture)
     * t 或 time：持久时间（单位 h），属于持久类别 (stress_rupture)
     * δ 或 delta：持久断后伸长率（单位 %），属于持久类别 (stress_rupture)
     * **特别注意**：持久试验表格中的延伸率通常带下标（如 δ₄），输出为 "delta_4"，属于持久类别 (stress_rupture)
     * **持久试验是一个整体**：试验温度、应力、持久时间、断后伸长率必须合并到同一条 stress_rupture 数据中，不要拆分
   - **试验温度**：识别表格标题或文字中的温度值（如"704℃拉伸性能"、"试验温度：704℃"、"室温拉伸性能"）
     * 提取温度数值和单位，输出到 **test_values** 中的 "test_temperature" 字段
     * 示例："704℃" → {"test_temperature":{"value":"704","unit":"℃"}}
     * 示例："室温" 或 "常温" → {"test_temperature":{"value":"室温","unit":"℃"}}
     * 示例："20℃" 或 "20°C" → {"test_temperature":{"value":"20","unit":"℃"}}
     * 示例："-40℃" → {"test_temperature":{"value":"-40","unit":"℃"}}
     * **注意**：试验温度是文本类型，如果是"室温"直接输出"室温"，不要转换成数字
     * **重要**：必须放在 test_values 中，不要放在 additional_conditions 中
5. **数字下标识别**：仔细识别δ的下标数字，4 和 5 容易混淆，需根据图片实际内容判断
6. **宏观组织（低倍）检验特殊处理**：
   - **识别章节结构**：如果图片中有"3.7 低倍"、"3.7.1"、"3.7.2"、"3.7.3"等章节编号，这些都是低倍检验的内容
   - **文字内容合并**：3.7.1、3.7.2 等小节的所有文字描述（如金属流线方向、低倍组织缺陷要求）都属于低倍判定指标
   - **表格内容解析**：3.7.3 等小节下的表格（如缺陷类型表）需要解析表格中的缺陷类型和级别要求
   - **整合输出**：将文字描述和表格要求整合到一条 macro_structure_desctription 数据中
   - **示例**：
     * 3.7.1 金属流线方向描述 → 低倍判定指标
     * 3.7.2 低倍组织缺陷描述 → 低倍判定指标
     * 3.7.3 表格：暗斑 A 级、白斑 A 级、径向偏析 B 级、环状花样 B 级 → 低倍判定指标
     * 最终输出：将所有内容合并为一段完整的描述
   - **【关键】输出格式**：必须将完整的判定指标描述放到 **test_values.macro_structure_desctription** 字段中，格式为：
     * {"macro_structure_desctription":{"value":"完整的判定指标描述文字"}}
     * **不要**放到 remarks 字段中，remarks 只用于存放额外的备注信息
7. **晶粒度检验特殊处理**：
   - **识别章节结构**：如果图片中有"3.8 晶粒度"、"3.8.1"、"3.8.2"等章节编号，这些都是晶粒度检验的内容
   - **文字内容识别**：晶粒度章节中的所有文字描述（如热处理制度、晶粒度级别要求）都属于晶粒度判定指标
   - **关键特征词**：当图片中出现"晶粒度"、"晶粒级别"、"晶粒尺寸"、"grain size"等关键词时，应识别为晶粒度类别
   - **输出格式**：将晶粒度要求放到 **test_values.grain_size_description** 字段中
   - **示例**：
     * "3.8 晶粒度" → 晶粒度检验
     * "晶粒度试样加热到 885±15℃，保温 60min" → 热处理制度
     * "直径不大于 300mm 的棒材锻制的锻件晶粒度级别大于等于 8 级" → 晶粒度要求
     * 最终输出：test_category_code="grain_size", test_values.grain_size_description="完整的描述"
8. **牌号识别示例**：
   - 如果表格第一列显示 "30Si2MnCrMoVE" 和 "31Si2MnCrMoVE" 两行
   - 必须输出 2 条数据，alloy_grade 分别是 "30Si2MnCrMoVE" 和 "31Si2MnCrMoVE"
   - 即使它们的热处理制度相同，也必须分别输出

数据库字段要求：
- material_spec_number: 编号，如 "GJB 2351A-2021"、"GB/T 1499.2-2007"，**如果图片中没有明确的标准号，必须设为空字符串 ""，绝对不能编造**
- alloy_grade: 牌号，如 "2A02"、"GH4169"、"304"、"30Si2MnCrMoVE"、"31Si2MnCrMoVE"
- status: 状态，如 "T6"、"固溶"、"退火"、"正火 + 淬火 + 回火"
- specification: 规格，如 "Φ20mm"、"板状"、"-"
- sampling_direction: 取样方向，如 "纵向"、"横向"
- test_category_code: 类别代码，如 "chemical_composition"、"tension"、"impact"、"fracture_toughness"

数值字段规则：
- 范围值 0.015~0.060 → {"min_value":"0.015","max_value":"0.060"}
- **【必须】大于等于 ≥390 或表格标题包含"不小于"时 → {"min_value":"390","comparison":">=","unit":"MPa"}**
- **【必须】小于等于 ≤0.01 或表格标题包含"不大于"时 → {"max_value":"0.01","comparison":"<=","unit":"%"}**
- 单值 → {"value":"0.75"}
- **【关键】如果材料性能表中标题或表头有"不小于"、"≥"、"最小值"、"min"等表示最小要求的词，必须添加 comparison:">="**
- **【关键】如果材料性能表中标题或表头有"不大于"、"≤"、"最大值"、"max"等表示最大要求的词，必须添加 comparison:"<="**
- 保留原始精度：55.0 必须写成 55.0，不能写成 55；0.060 必须写成 0.060
- **试验温度**：从表格标题或文字中提取温度值
  * 高温示例："704℃拉伸性能"→ {"test_temperature":{"value":"704","unit":"℃"}}
  * 室温示例："室温拉伸性能"→ {"test_temperature":{"value":"室温","unit":"℃"}}
  * 文本类型，直接输出识别到的温度描述
  * **重要**：必须放在 test_values 中，不要放在 additional_conditions 中

**【新增字段】item_key 和 experimental_conditions**：
- **item_key**：项目关键字数组，用于查询匹配。根据试验条件自动生成
  - 化学成分：["化学成分"]
  - 拉伸高温（704℃等）：["高温", "抗拉"] 或 ["高温", "屈服"]
  - 拉伸室温：["室温", "抗拉"] 或 ["室温", "屈服"]
  - 冲击高温：["高温", "冲击"]
  - 冲击低温（-40℃等）：["低温", "冲击"]
  - 持久/蠕变：["持久"] 或 ["蠕变"]
  - 硬度：["硬度"]
- **experimental_conditions**：试验条件 JSON 格式
  - 高温（如704℃）：{"temperature": "704℃"}
  - 低温（如-40℃）：{"temperature": "-40℃"}
  - 持久：{"temperature": "750℃", "stress": "XXX MPa", "test_time": "100h"}
  - **注意**：试验温度必须从表格标题或文本中提取（如"704℃拉伸性能"中的"704℃"）

请严格按照以下 JSON 格式输出，只返回 JSON，不要其他文字：
""" + json_output_example
        
        return prompt

    def _extract_json(self, result_text: str) -> List[Dict]:
        """
        从模型响应中提取 JSON 数据
        支持多种响应格式：
        1. {"specs": [...]} - 标准格式
        2. {"data": [...]} - 可能的替代格式
        3. [{...}, {...}] - 直接数组格式
        4. {"standard": ..., "material": ..., ...} - 单条数据简化格式
        """
        try:
            # 记录原始响应
            logger.info(f"[Vision] 原始响应前200字符: {result_text[:200]}")
            
            # 尝试找到 JSON 边界
            json_start = result_text.find('{')
            json_end = result_text.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = result_text[json_start:json_end]
                result = json.loads(json_str)
                
                # 情况1: 标准格式 {"specs": [...]}
                if 'specs' in result:
                    specs = result.get('specs', [])
                    logger.info(f"[Vision] 使用 specs 格式，解析得到 {len(specs)} 条数据")
                    return specs
                
                # 情况2: 替代格式 {"data": [...]}
                if 'data' in result and isinstance(result['data'], list):
                    logger.info(f"[Vision] 使用 data 格式，解析得到 {len(result['data'])} 条数据")
                    return result['data']
                
                # 情况3: 直接数组格式 [...]
                if isinstance(result, list):
                    logger.info(f"[Vision] 使用直接数组格式，解析得到 {len(result)} 条数据")
                    return result
                
                # 情况4: 单条数据简化格式 {"standard": ..., "material": ...}
                # 尝试将简化格式转换为标准格式
                simplified_spec = self._convert_simplified_format(result)
                if simplified_spec:
                    logger.info(f"[Vision] 使用简化格式转换，得到 1 条数据")
                    return [simplified_spec]
                
                # 未能解析
                logger.warning(f"[Vision] 响应中未找到 'specs' 或 'data' 字段")
                logger.warning(f"[Vision] 响应 keys: {list(result.keys())}")
                return []
            else:
                logger.warning(f"[Vision] 无法找到 JSON 边界")
                return []
                
        except json.JSONDecodeError as e:
            logger.error(f"[Vision] JSON 解析失败：{e}")
            logger.error(f"[Vision] 原始响应：{result_text}")
            return []
        except Exception as e:
            logger.error(f"[Vision] 解析异常：{e}")
            logger.error(f"[Vision] 原始响应：{result_text}")
            return []
    
    def _convert_simplified_format(self, result: Dict) -> Dict:
        """
        将简化格式的响应转换为标准格式
        简化格式如: {"standard": "...", "material": "...", "grade": "...", ...}
        """
        import re
        
        # 检查是否是简化格式（包含特定字段）
        simplified_keys = {'standard', 'material', 'grade', 'diameter', 'tensile_strength', 
                          'yield_strength', 'extension_rate'}
        
        if not any(key in result for key in simplified_keys):
            return None
        
        spec = {
            'material_spec_number': result.get('standard', '') or result.get('spec_number', '') or result.get('specification', ''),
            'alloy_grade': result.get('material', '') or result.get('grade', '') or result.get('alloy', ''),
            'status': result.get('status', '') or result.get('state', ''),
            'specification': result.get('diameter', '') or result.get('spec', ''),
            'sampling_direction': result.get('direction', '') or result.get('sample_direction', '-'),
            'test_category_code': 'tension',  # 默认拉伸类别，后续可调整
            'test_values': {},
            'additional_conditions': {},
            'remarks': result.get('remark', '') or result.get('notes', '')
        }
        
        # 解析拉伸强度
        tensile = result.get('tensile_strength', '') or result.get('tensile', '')
        if tensile:
            tensile_data = self._parse_value_with_comparison(tensile, 'σ_b')
            if tensile_data:
                spec['test_values']['σ_b'] = tensile_data
        
        # 解析屈服强度
        yield_strength = result.get('yield_strength', '') or result.get('yield', '')
        if yield_strength:
            yield_data = self._parse_value_with_comparison(yield_strength, 'σ_0.2')
            if yield_data:
                spec['test_values']['σ_0.2'] = yield_data
        
        # 解析伸长率
        extension = result.get('extension_rate', '') or result.get('elongation', '') or result.get('delta', '')
        if extension:
            elongation_data = self._parse_value_with_comparison(extension, 'δ_5')
            if elongation_data:
                spec['test_values']['δ_5'] = elongation_data
        
        # 解析冲击能量
        impact = result.get('impact_energy', '') or result.get('impact', '')
        if impact:
            impact_data = self._parse_value_with_comparison(impact, 'A_Ku2')
            if impact_data:
                spec['test_values']['A_Ku2'] = impact_data
        
        # 根据检测到的字段确定测试类别
        if 'A_Ku2' in spec['test_values'] and 'σ_b' not in spec['test_values']:
            spec['test_category_code'] = 'impact'
        elif 'σ_b' in spec['test_values']:
            spec['test_category_code'] = 'tension'
        
        # 设置默认值
        if not spec['material_spec_number']:
            spec['material_spec_number'] = '-'
        if not spec['alloy_grade']:
            spec['alloy_grade'] = '-'
        if not spec['status']:
            spec['status'] = '-'
        if not spec['specification']:
            spec['specification'] = '-'
        if not spec['sampling_direction']:
            spec['sampling_direction'] = '-'
        
        logger.info(f"[Vision] 简化格式转换完成: material_spec_number={spec['material_spec_number']}, alloy_grade={spec['alloy_grade']}, test_category_code={spec['test_category_code']}")
        
        return spec
    
    def _parse_value_with_comparison(self, value_str: str, field_code: str) -> Dict:
        """
        解析值字符串，提取数值和比较符
        例如: "σ_b ≥ 1620 MPa" -> {"min_value": "1620", "comparison": ">=", "unit": "MPa"}
        """
        import re
        
        result = {'value': value_str}  # 保留原始值
        
        # 尝试提取比较符
        if '≥' in value_str or '不小于' in value_str or '≥' in value_str:
            result['comparison'] = '≥'
            # 提取数值
            match = re.search(r'(\d+\.?\d*)', value_str)
            if match:
                result['min_value'] = match.group(1)
                result.pop('value', None)
        elif '≤' in value_str or '不大于' in value_str:
            result['comparison'] = '≤'
            match = re.search(r'(\d+\.?\d*)', value_str)
            if match:
                result['max_value'] = match.group(1)
                result.pop('value', None)
        elif '>' in value_str:
            result['comparison'] = '>'
            match = re.search(r'(\d+\.?\d*)', value_str)
            if match:
                result['min_value'] = match.group(1)
                result.pop('value', None)
        elif '<' in value_str:
            result['comparison'] = '<'
            match = re.search(r'(\d+\.?\d*)', value_str)
            if match:
                result['max_value'] = match.group(1)
                result.pop('value', None)
        else:
            # 尝试提取数值
            match = re.search(r'(\d+\.?\d*)', value_str)
            if match:
                result['value'] = match.group(1)
        
        # 提取单位
        units = ['MPa', 'J', '%', 'HRC', 'HB', 'HV', '℃', '°C']
        for unit in units:
            if unit in value_str:
                result['unit'] = unit
                break
        
        return result
    
    def _infer_comparison(self, specs: List[Dict]) -> List[Dict]:
        """根据字段类型自动推断 comparison
        材料性能表中，屈服强度、抗拉强度、伸长率、冲击能量、断裂韧度等都是"不小于"要求
        """
        min_requirement_fields = {
            'sigma_0.2', 'sigma_b', 'sigma_s', 'sigma',
            'delta_5', 'delta', 'elongation', 'elongation_4d', 'elongation_5d', 'elongation_10d', 'elongation_11d',
            'psi', 'reduction_of_area',
            'A_Ku2', 'A_ku2', 'impact_energy', 'KV2', 'KV8',
            'K_IC', 'K_Ic', 'fracture_toughness',
            'HB', 'HRC', 'HV', 'hardness'
        }
        
        for spec in specs:
            test_values = spec.get('test_values', {})
            for field_name, field_data in test_values.items():
                if not isinstance(field_data, dict):
                    continue
                
                if field_data.get('comparison'):
                    continue
                
                field_lower = field_name.lower()
                if field_lower in min_requirement_fields or any(f in field_lower for f in min_requirement_fields):
                    if 'value' in field_data:
                        field_data['min_value'] = field_data.pop('value')
                    field_data['comparison'] = '≥'
                    logger.info(f"[推断] 字段 {field_name} 添加 comparison: ≥")
        
        specs = self._process_grain_size_specs(specs)
        
        return specs
    
    def _process_grain_size_specs(self, specs: List[Dict]) -> List[Dict]:
        """
        晶粒度特殊处理：拆分预处理、规格、判定要求，生成多条记录
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
            else:
                new_spec = spec.copy()
                new_spec['test_values'] = spec.get('test_values', {}).copy()
                new_spec['test_values']['grain_size_description'] = requirement_text
                new_spec['specification'] = spec.get('specification', '-') or '-'
                new_spec['remarks'] = preprocessing_text.strip('，。、, ') if preprocessing_text else spec.get('remarks', '')
                result_specs.append(new_spec)
        
        return result_specs
