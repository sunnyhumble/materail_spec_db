from flask import Flask, render_template, request, jsonify, send_from_directory, Response
from collections import OrderedDict
from werkzeug.utils import secure_filename
import os
import json
import base64
import time
from dotenv import load_dotenv

load_dotenv()

from config import DATABASE_PATH, DATABASE_URL, API_KEY, API_BASE_URL, API_MODEL, VISION_MODEL, ALLOWED_EXTENSIONS
from database.operations import MaterialDatabase
from parser.vision_parser import VisionMaterialParser
from utils.import_converter import convert_import_data

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
app.config['JSON_SORT_KEYS'] = False

# 优先使用PostgreSQL，备选使用SQLite
db = MaterialDatabase(db_url=DATABASE_URL)

_vision_parser_instance = None

def get_ocr_parser():
    global _vision_parser_instance
    if _vision_parser_instance is None:
        _vision_parser_instance = VisionMaterialParser(API_KEY, API_BASE_URL, VISION_MODEL)
        print(f"[初始化] Vision Parser 实例创建成功，模型: {VISION_MODEL}")
    return _vision_parser_instance


def _normalize_recognize_result(specs):
    """对识别结果做最终规范化：category_code 别名 + comparison 符号 + 试验条件默认室温

    之所以在 API 层再做一次，是因为 _split_specs_by_category 会在
    parser 返回前/后重新生成 test_values，覆盖 parser 内部的规范化结果。
    """
    from database.operations import (
        _normalize_category_code as _norm_cat,
        _normalize_comparison as _norm_cmp,
        _normalize_experimental_conditions as _norm_exp,
    )
    if not isinstance(specs, list):
        return specs
    for spec in specs:
        if not isinstance(spec, dict):
            continue
        # 1) 类别代码规范化（LLM 输出的拼写错误 → 数据库定义的标准代码）
        spec['test_category_code'] = _norm_cat(spec.get('test_category_code', ''))
        cat = spec['test_category_code']

        # 2) test_values 字段规范化
        tv = spec.get('test_values', {})
        if isinstance(tv, dict):
            for _field_code, field_data in tv.items():
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
    return specs



def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/categories', methods=['GET'])
def get_categories():
    try:
        categories = db.get_test_categories()
        return jsonify({'success': True, 'data': categories})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/category/<code>', methods=['GET'])
def get_category(code):
    try:
        category = db.get_category_by_code(code)
        if category:
            return jsonify({'success': True, 'data': category})
        return jsonify({'success': False, 'error': '类别不存在'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/specs', methods=['GET', 'POST'])
def handle_specs():
    if request.method == 'GET':
        try:
            filters = {
                'material_spec_number': request.args.get('spec_number', ''),
                'specification': request.args.get('specification', ''),
                'alloy_grade': request.args.get('alloy_grade', ''),
                'status': request.args.get('status', ''),
                'sampling_direction': request.args.get('sampling_direction', ''),
                'test_category_code': request.args.get('test_category_code', ''),
                'update_time': request.args.get('update_time', '')
            }
            filters = {k: v for k, v in filters.items() if v}
            specs = db.query_specs(**filters)
            return jsonify({'success': True, 'data': specs})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    
    elif request.method == 'POST':
        try:
            data = request.get_json()
            spec_id = db.add_spec(data)
            return jsonify({'success': True, 'id': spec_id})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/specs/<int:spec_id>', methods=['GET', 'PUT', 'DELETE'])
def handle_spec(spec_id):
    if request.method == 'GET':
        try:
            specs = db.query_specs()
            spec = next((s for s in specs if s['id'] == spec_id), None)
            if spec:
                return jsonify({'success': True, 'data': spec})
            return jsonify({'success': False, 'error': '规范不存在'}), 404
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    
    elif request.method == 'PUT':
        try:
            data = request.get_json()
            db.update_spec(spec_id, data)
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 400
    
    elif request.method == 'DELETE':
        try:
            db.delete_spec(spec_id)
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/query', methods=['POST'])
def query_specs_post():
    """POST endpoint for querying specs"""
    try:
        data = request.get_json() or {}
        filters = {
            'material_spec_number': data.get('material_spec_number', ''),
            'specification': data.get('specification', ''),
            'alloy_grade': data.get('alloy_grade', ''),
            'status': data.get('status', ''),
            'sampling_direction': data.get('sampling_direction', ''),
            'test_category_code': data.get('test_category_code', ''),
            'update_time': data.get('update_time', '')
        }
        # Remove empty filters
        filters = {k: v for k, v in filters.items() if v}
        specs = db.query_specs(**filters)
        # Return ordered response: success, query, data
        response = OrderedDict([
            ('success', True),
            ('query', data),
            ('data', specs)
        ])
        return Response(
            json.dumps(response, ensure_ascii=False),
            mimetype='application/json'
        )
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/statistics', methods=['GET'])
def get_statistics():
    try:
        stats = db.get_statistics()
        return jsonify({'success': True, 'data': stats})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/alloy-grades', methods=['GET'])
def get_alloy_grades():
    try:
        grades = db.get_all_alloy_grades()
        return jsonify({'success': True, 'data': grades})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/spec-numbers', methods=['GET'])
def get_spec_numbers():
    try:
        numbers = db.get_all_spec_numbers()
        return jsonify({'success': True, 'data': numbers})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/parse-image', methods=['POST'])
def parse_image():
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': '没有文件'}), 400
        
        file = request.files['file']
        test_category_code = request.form.get('test_category_code', '')
        
        if file.filename == '':
            return jsonify({'success': False, 'error': '未选择文件'}), 400
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config.get('UPLOAD_FOLDER', 'uploads'), filename)
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            file.save(filepath)
            
            parser = get_ocr_parser()
            with open(filepath, 'rb') as f:
                base64_data = base64.b64encode(f.read()).decode('utf-8')
            specs = parser.parse_image_from_base64(base64_data, test_category_code)

            from parser.hybrid_parser import HybridMaterialParser
            parser_helper = HybridMaterialParser.__new__(HybridMaterialParser)
            original_count = len(specs)
            specs = parser_helper._split_specs_by_category(specs)
            print(f"[API拆分] {original_count} 条 → {len(specs)} 条")

            # API 层规范化（_split_specs_by_category 会重新生成 test_values，需再次规范化）
            specs = _normalize_recognize_result(specs)

            os.remove(filepath)

            return jsonify({'success': True, 'data': specs})
        
        return jsonify({'success': False, 'error': '不支持的文件类型'}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/parse-image-base64', methods=['POST'])
def parse_image_base64():
    try:
        start_time = time.time()
        data = request.get_json()
        image_data = data.get('image_data')
        test_category_code = data.get('test_category_code', '')
        
        if not image_data:
            return jsonify({'success': False, 'error': '没有图片数据'}), 400
        
        parser = get_ocr_parser()
        specs = parser.parse_image_from_base64(image_data, test_category_code)

        # 在 API 层面添加强制拆分逻辑（确保执行）
        from parser.hybrid_parser import HybridMaterialParser
        parser_helper = HybridMaterialParser.__new__(HybridMaterialParser)
        original_count = len(specs)
        specs = parser_helper._split_specs_by_category(specs)
        print(f"[API拆分] {original_count} 条 → {len(specs)} 条")

        # API 层规范化（_split_specs_by_category 会重新生成 test_values，需再次规范化）
        specs = _normalize_recognize_result(specs)

        elapsed = time.time() - start_time
        print(f"[性能] 图片识别总耗时：{elapsed:.2f}秒，识别到 {len(specs)} 条数据")

        return jsonify({'success': True, 'data': specs, 'elapsed': round(elapsed, 2)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500



@app.route('/api/batch-import', methods=['POST'])
def batch_import():
    try:
        data = request.get_json()
        specs = data.get('specs', [])
        
        if not specs:
            return jsonify({'success': False, 'error': '没有数据'}), 400
        
        converted_specs = convert_import_data(specs)
        
        imported_count = 0
        skipped_count = 0
        duplicates = []
        errors = []
        
        for i, spec in enumerate(converted_specs):
            try:
                print(f"[导入调试] 第 {i} 条数据：")
                print(f"  - test_category_code: {spec.get('test_category_code')}")
                print(f"  - test_values 原始：{spec.get('test_values', {})}")
                
                if 'test_values' in spec:
                    category_code = spec.get('test_category_code')
                    spec['test_values'] = db.apply_field_mappings(spec['test_values'], category_code)
                    print(f"  - test_values 映射后：{spec.get('test_values', {})}")
                
                db.add_spec(spec)
                imported_count += 1
                print(f"[导入调试] 导入成功")
            except ValueError as e:
                error_msg = str(e)
                print(f"[导入调试] ValueError: {error_msg}")
                if '数据已存在' in error_msg:
                    skipped_count += 1
                    duplicates.append({
                        'index': i,
                        'spec_number': spec.get('spec_number'),
                        'alloy_grade': spec.get('alloy_grade'),
                        'existing_id': error_msg.split('记录 ID: ')[-1] if '记录 ID: ' in error_msg else None
                    })
                else:
                    errors.append({'index': i, 'error': error_msg})
            except Exception as e:
                import traceback
                print(f"[导入调试] Exception: {str(e)}")
                print(f"[导入调试] 详细错误: {traceback.format_exc()}")
                errors.append({'index': i, 'error': str(e)})
        
        return jsonify({
            'success': True,
            'imported_count': imported_count,
            'skipped_count': skipped_count,
            'duplicates': duplicates,
            'errors': errors
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# 字段管理 API
@app.route('/api/admin/categories', methods=['GET', 'POST'])
def handle_categories():
    if request.method == 'GET':
        try:
            categories = db.get_all_test_categories()
            return jsonify({'success': True, 'data': categories})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    elif request.method == 'POST':
        try:
            data = request.get_json()
            name = data.get('name')
            code = data.get('code')
            fields = data.get('fields', [])
            description = data.get('description')
            
            if not name or not code:
                return jsonify({'success': False, 'error': '缺少名称或代码'}), 400
            
            category_id = db.add_custom_test_category(name, code, fields, description)
            return jsonify({'success': True, 'id': category_id})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/admin/categories/<int:category_id>', methods=['PUT', 'DELETE'])
def handle_category(category_id):
    if request.method == 'PUT':
        try:
            data = request.get_json()
            name = data.get('name')
            code = data.get('code')
            description = data.get('description')
            is_active = data.get('is_active')
            sort_order = data.get('sort_order')
            
            db.update_test_category(category_id, name, code, description, is_active, sort_order)
            
            # 处理字段的更新
            fields = data.get('fields', [])
            if fields:
                # 先获取现有字段
                existing_fields = db.get_test_category_fields(category_id)
                existing_codes = {f['field_code']: f['id'] for f in existing_fields}
                updated_codes = set()
                
                for field_data in fields:
                    field_code = field_data.get('field_code')
                    if field_code in existing_codes:
                        # 更新现有字段
                        field_id = existing_codes[field_code]
                        db.update_test_field(
                            field_id,
                            field_data.get('field_name'),
                            field_data.get('field_code'),
                            field_data.get('field_type'),
                            field_data.get('unit'),
                            field_data.get('description'),
                            field_data.get('is_required'),
                            field_data.get('sort_order')
                        )
                        updated_codes.add(field_code)
                    else:
                        # 添加新字段
                        db.add_test_field(
                            category_id,
                            field_data.get('field_name'),
                            field_data.get('field_code'),
                            field_data.get('field_type'),
                            field_data.get('unit'),
                            field_data.get('description'),
                            field_data.get('is_required'),
                            field_data.get('sort_order')
                        )
                
                # 删除不在新列表中的字段
                for code, field_id in existing_codes.items():
                    if code not in updated_codes:
                        try:
                            db.delete_test_field(field_id)
                        except:
                            pass  # 可能有依赖关系，删除失败则忽略
            
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 400
    elif request.method == 'DELETE':
        try:
            db.delete_test_category(category_id)
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/admin/fields', methods=['POST'])
def add_field():
    try:
        data = request.get_json()
        category_id = data.get('category_id')
        field_name = data.get('field_name')
        field_code = data.get('field_code')
        field_type = data.get('field_type')
        unit = data.get('unit')
        description = data.get('description')
        is_required = data.get('is_required', False)
        sort_order = data.get('sort_order', 0)
        
        if not category_id or not field_name or not field_code or not field_type:
            return jsonify({'success': False, 'error': '缺少必填字段'}), 400
        
        field_id = db.add_test_field(category_id, field_name, field_code, field_type, unit, description, is_required, sort_order)
        return jsonify({'success': True, 'id': field_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/admin/fields/<int:field_id>', methods=['PUT', 'DELETE'])
def handle_field(field_id):
    if request.method == 'PUT':
        try:
            data = request.get_json()
            field_name = data.get('field_name')
            field_code = data.get('field_code')
            field_type = data.get('field_type')
            unit = data.get('unit')
            description = data.get('description')
            is_required = data.get('is_required')
            sort_order = data.get('sort_order')
            
            db.update_test_field(field_id, field_name, field_code, field_type, unit, description, is_required, sort_order)
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 400
    elif request.method == 'DELETE':
        try:
            db.delete_test_field(field_id)
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/admin/field-mappings', methods=['GET', 'POST'])
def handle_field_mappings():
    if request.method == 'GET':
        try:
            category_code = request.args.get('category_code')
            active_only = request.args.get('active_only', 'true').lower() == 'true'
            source_field = request.args.get('source_field')
            target_field_code = request.args.get('target_field_code')
            merge_sources = request.args.get('merge_sources', 'true').lower() == 'true'
            mappings = db.get_field_mappings(category_code, active_only, source_field, target_field_code, merge_sources)
            print(f"[字段映射] 返回 {len(mappings)} 条映射 (category={category_code}, active_only={active_only}, source_field={source_field}, target_field_code={target_field_code}, merge_sources={merge_sources})")
            return jsonify({'success': True, 'data': mappings})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    elif request.method == 'POST':
        try:
            data = request.get_json()
            source_fields = data.get('source_fields')
            target_field_code = data.get('target_field_code')
            category_code = data.get('category_code')
            
            if not source_fields or not target_field_code:
                return jsonify({'success': False, 'error': '缺少源字段或目标字段代码'}), 400
            
            db.add_field_mapping(source_fields, target_field_code, category_code)
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/admin/field-mappings/<int:mapping_id>', methods=['PUT', 'DELETE'])
def handle_field_mapping(mapping_id):
    if request.method == 'PUT':
        try:
            data = request.get_json()
            source_fields = data.get('source_fields')
            target_field_code = data.get('target_field_code')
            category_code = data.get('category_code')
            is_active = data.get('is_active')
            
            db.update_field_mapping(mapping_id, source_fields, target_field_code, category_code, is_active)
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 400
    elif request.method == 'DELETE':
        try:
            db.delete_field_mapping(mapping_id)
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 400

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5005)
