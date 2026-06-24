from sqlalchemy import create_engine, Column, Integer, String, Float, Text, ForeignKey, Boolean, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class TestCategory(Base):
    __tablename__ = 'test_categories'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True, comment='测试类别名称')
    code = Column(String(50), nullable=False, unique=True, comment='类别代码')
    description = Column(Text, comment='描述')
    is_active = Column(Boolean, default=True, comment='是否启用')
    sort_order = Column(Integer, default=0, comment='排序')
    created_at = Column(DateTime, default=datetime.now)
    
    field_definitions = relationship("TestFieldDefinition", back_populates="category", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<TestCategory {self.name}>"

class TestFieldDefinition(Base):
    __tablename__ = 'test_field_definitions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    category_id = Column(Integer, ForeignKey('test_categories.id'), nullable=False)
    field_name = Column(String(100), nullable=False, comment='字段名称')
    field_code = Column(String(50), nullable=False, comment='字段代码')
    field_type = Column(String(20), nullable=False, comment='字段类型')
    unit = Column(String(50), comment='默认单位')
    description = Column(Text, comment='字段描述')
    is_required = Column(Boolean, default=False, comment='是否必填')
    sort_order = Column(Integer, default=0, comment='排序')
    
    category = relationship("TestCategory", back_populates="field_definitions")
    
    def __repr__(self):
        return f"<TestFieldDefinition {self.field_name}>"

class MaterialSpec(Base):
    __tablename__ = 'material_specs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    material_spec_number = Column(String(100), nullable=False, comment='编号')
    test_category_id = Column(Integer, ForeignKey('test_categories.id'), nullable=False, comment='类别ID')
    alloy_grade = Column(String(100), nullable=False, comment='牌号')
    status = Column(String(100), nullable=False, comment='状态')
    specification = Column(String(200), nullable=False, comment='规格')
    sampling_direction = Column(String(50), nullable=False, comment='取样方向')
    
    test_category = relationship("TestCategory")
    test_values = relationship("TestValue", back_populates="spec", cascade="all, delete-orphan")
    
    additional_conditions = Column(Text, comment='附加条件(JSON)')
    remarks = Column(Text, comment='备注')
    
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    def __repr__(self):
        return f"<MaterialSpec {self.material_spec_number} {self.alloy_grade}>"

class TestValue(Base):
    __tablename__ = 'test_values'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    spec_id = Column(Integer, ForeignKey('material_specs.id'), nullable=False)
    field_definition_id = Column(Integer, ForeignKey('test_field_definitions.id'), nullable=False)
    
    # 项目关键字（JSON数组格式，支持多个关键字，用于查询匹配）
    item_key = Column(Text, comment='项目关键字(JSON数组)，如["高温","抗拉"]，查询时匹配任一关键字即可')
    string_value = Column(Text, comment='字符串值')
    number_value = Column(String(50), comment='数值')
    min_value = Column(String(50), comment='最小值')
    max_value = Column(String(50), comment='最大值')
    comparison = Column(String(20), comment='比较符号')
    unit = Column(String(50), comment='实际单位')
    
    # 试验条件（JSON格式存储，如温度、应力等）
    experimental_conditions = Column(Text, comment='试验条件(JSON)')
    
    spec = relationship("MaterialSpec", back_populates="test_values")
    field_definition = relationship("TestFieldDefinition")
    
    def __repr__(self):
        return f"<TestValue {self.field_definition.field_name}>"


class ExperimentalConditionField(Base):
    """试验条件字段定义表"""
    __tablename__ = 'experimental_condition_fields'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    field_code = Column(String(50), nullable=False, comment='字段代码')
    field_name = Column(String(100), nullable=False, comment='字段名称')
    field_type = Column(String(20), comment='字段类型：number, text')
    unit = Column(String(50), comment='单位')
    description = Column(Text, comment='描述')
    sort_order = Column(Integer, default=0, comment='排序')
    
    def __repr__(self):
        return f"<ExperimentalConditionField {self.field_name}>"


class ConditionConstraint(Base):
    """试验条件约束表"""
    __tablename__ = 'condition_constraints'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    category_id = Column(Integer, ForeignKey('test_categories.id'), comment='测试类别ID')
    field_code = Column(String(50), comment='试验条件字段代码')
    is_required = Column(Boolean, default=False, comment='是否必填')
    is_allowed = Column(Boolean, default=True, comment='是否允许填写')
    mutually_exclusive_group = Column(String(50), comment='互斥字段组名称')
    
    category = relationship("TestCategory")
    
    def __repr__(self):
        return f"<ConditionConstraint category={self.category_id} field={self.field_code}>"


class FieldMapping(Base):
    __tablename__ = 'field_mappings'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    source_field = Column(String(100), nullable=False, comment='识别的字段名（可能包含错误）')
    target_field_code = Column(String(50), nullable=False, comment='目标字段代码')
    category_code = Column(String(50), ForeignKey('test_categories.code'), comment='适用的类别代码')
    is_active = Column(Boolean, default=True, comment='是否启用')
    created_at = Column(DateTime, default=datetime.now)
    
    category = relationship("TestCategory")
    
    def __repr__(self):
        return f"<FieldMapping {self.source_field} -> {self.target_field_code}>"

def init_default_categories(session):
    default_categories = [
        {
            'name': '化学成分',
            'code': 'chemical_composition',
            'description': '材料化学成分分析',
            'fields': [
                {'field_name': 'C', 'field_code': 'c', 'field_type': 'range', 'unit': '%'},
                {'field_name': 'Cr', 'field_code': 'cr', 'field_type': 'range', 'unit': '%'},
                {'field_name': 'Mo', 'field_code': 'mo', 'field_type': 'range', 'unit': '%'},
                {'field_name': 'Al', 'field_code': 'al', 'field_type': 'range', 'unit': '%'},
                {'field_name': 'Ti', 'field_code': 'ti', 'field_type': 'range', 'unit': '%'},
                {'field_name': 'Co', 'field_code': 'co', 'field_type': 'range', 'unit': '%'},
                {'field_name': 'B', 'field_code': 'b', 'field_type': 'range', 'unit': '%'},
                {'field_name': 'Ni', 'field_code': 'ni', 'field_type': 'range', 'unit': '%'},
                {'field_name': 'Si', 'field_code': 'si', 'field_type': 'range', 'unit': '%'},
                {'field_name': 'Mn', 'field_code': 'mn', 'field_type': 'range', 'unit': '%'},
                {'field_name': 'S', 'field_code': 's', 'field_type': 'range', 'unit': '%'},
                {'field_name': 'P', 'field_code': 'p', 'field_type': 'range', 'unit': '%'},
                {'field_name': 'Zr', 'field_code': 'zr', 'field_type': 'range', 'unit': '%'},
                {'field_name': 'Cu', 'field_code': 'cu', 'field_type': 'range', 'unit': '%'},
                {'field_name': 'Fe', 'field_code': 'fe', 'field_type': 'range', 'unit': '%'},
                {'field_name': 'Pb', 'field_code': 'pb', 'field_type': 'range', 'unit': '%'},
                {'field_name': 'As', 'field_code': 'as', 'field_type': 'range', 'unit': '%'},
                {'field_name': 'Sn', 'field_code': 'sn', 'field_type': 'range', 'unit': '%'},
                {'field_name': 'Sb', 'field_code': 'sb', 'field_type': 'range', 'unit': '%'},
                {'field_name': 'Bi', 'field_code': 'bi', 'field_type': 'range', 'unit': '%'},
                {'field_name': 'Ag', 'field_code': 'ag', 'field_type': 'range', 'unit': '%'},
                {'field_name': 'Nb', 'field_code': 'nb', 'field_type': 'range', 'unit': '%'},
                {'field_name': 'Mg', 'field_code': 'mg', 'field_type': 'range', 'unit': '%'},
            ]
        },
        {
            'name': '拉伸',
            'code': 'tension',
            'description': '拉伸性能试验',
            'fields': [
                {'field_name': '抗拉强度 Rm', 'field_code': 'tensile_strength', 'field_type': 'range', 'unit': 'MPa'},
                {'field_name': '屈服强度 Rp0.2', 'field_code': 'yield_strength', 'field_type': 'range', 'unit': 'MPa'},
                {'field_name': '规定塑性延伸强度 Rp1.0', 'field_code': 'proof_strength', 'field_type': 'range', 'unit': 'MPa'},
                {'field_name': '上屈服强度 ReH', 'field_code': 'upper_yield_strength', 'field_type': 'range', 'unit': 'MPa'},
                {'field_name': '下屈服强度 ReL', 'field_code': 'lower_yield_strength', 'field_type': 'range', 'unit': 'MPa'},
                {'field_name': '断面收缩率 Z', 'field_code': 'reduction_of_area', 'field_type': 'range', 'unit': '%'},
                {'field_name': '断后伸长率 A5D', 'field_code': 'elongation_5d', 'field_type': 'range', 'unit': '%'},
                {'field_name': '断后伸长率 A4D', 'field_code': 'elongation_4d', 'field_type': 'range', 'unit': '%'},
            ]
        },
        {
            'name': '冲击',
            'code': 'impact',
            'description': '冲击韧性试验',
            'fields': [
                {'field_name': '冲击吸收能量', 'field_code': 'impact_energy', 'field_type': 'range', 'unit': 'J'},
                {'field_name': '冲击吸收能量 AKu2', 'field_code': 'impact_energy_ku2', 'field_type': 'range', 'unit': 'J'},
                {'field_name': '冲击吸收能量 AKv2', 'field_code': 'impact_energy_kv2', 'field_type': 'range', 'unit': 'J'},
                {'field_name': 'A_Ku2', 'field_code': 'a_ku2', 'field_type': 'range', 'unit': 'J'},
            ]
        },
        {
            'name': '持久',
            'code': 'stress_rupture',
            'description': '持久强度试验',
            'fields': [
                {'field_name': '应力σ', 'field_code': 'stress', 'field_type': 'range', 'unit': 'MPa', 'is_required': True},
                {'field_name': '持续时间', 'field_code': 'rupture_time', 'field_type': 'range', 'unit': 'h'},
                {'field_name': '蠕变断面收缩率 Zu', 'field_code': 'creep_reduction_of_area', 'field_type': 'range', 'unit': '%'},
                {'field_name': '蠕变断后伸长率 δ4', 'field_code': 'creep_elongation_4d', 'field_type': 'range', 'unit': '%'},
                {'field_name': '蠕变断后伸长率 δ5', 'field_code': 'creep_elongation_5d', 'field_type': 'range', 'unit': '%'},
            ]
        },
        {
            'name': '蠕变',
            'code': 'creep',
            'description': '蠕变性能试验',
            'fields': [
                {'field_name': '应力', 'field_code': 'stress', 'field_type': 'number', 'unit': 'MPa', 'is_required': True},
                {'field_name': '持续时间', 'field_code': 'rupture_time', 'field_type': 'range', 'unit': 'h'},
                {'field_name': '残余变形', 'field_code': 'residual_deformation', 'field_type': 'range', 'unit': '%'},
                {'field_name': '蠕变断面收缩率 Zu', 'field_code': 'creep_reduction_of_area', 'field_type': 'range', 'unit': '%'},
                {'field_name': '蠕变断后伸长率 A4d', 'field_code': 'creep_elongation_4d', 'field_type': 'range', 'unit': '%'},
                {'field_name': '蠕变断后伸长率 A5d', 'field_code': 'creep_elongation_5d', 'field_type': 'range', 'unit': '%'},
            ]
        },
        {
            'name': '硬度',
            'code': 'hardness',
            'description': '硬度测试',
            'fields': [
                {'field_name': '硬度类型', 'field_code': 'hardness_type', 'field_type': 'string'},
                {'field_name': '标尺', 'field_code': 'scale', 'field_type': 'string'},
                {'field_name': '硬度值', 'field_code': 'hardness_value', 'field_type': 'range'},
            ]
        },
        {
            'name': '断裂韧度',
            'code': 'fracture_toughness',
            'description': '断裂韧度试验',
            'fields': [
                {'field_name': '断裂韧度 K_IC', 'field_code': 'fracture_toughness', 'field_type': 'range', 'unit': 'MPam^-1/2'},
            ]
        },
        {
            'name': '宏观组织',
            'code': 'macro_structure',
            'description': '宏观组织检验',
            'fields': [
                {'field_name': '宏观组织', 'field_code': 'macro_structure', 'field_type': 'text'},
            ]
        },
        {
            'name': '断口检验',
            'code': 'fracture_inspection',
            'description': '断口检验',
            'fields': [
                {'field_name': '要求描述', 'field_code': 'requirement_description', 'field_type': 'text'},
            ]
        },
        {
            'name': '晶粒度',
            'code': 'grain_size',
            'description': '晶粒度测定',
            'fields': [
                {'field_name': '要求描述', 'field_code': 'requirement_description', 'field_type': 'text'},
            ]
        },
        {
            'name': '非金属夹杂',
            'code': 'non_metallic_inclusion',
            'description': '非金属夹杂物评定',
            'fields': [
                {'field_name': '要求描述', 'field_code': 'requirement_description', 'field_type': 'text'},
            ]
        },
        {
            'name': '显微组织',
            'code': 'microstructure',
            'description': '显微组织检验',
            'fields': [
                {'field_name': '要求描述', 'field_code': 'requirement_description', 'field_type': 'text'},
            ]
        },
        {
            'name': '高周疲劳',
            'code': 'high_cycle_fatigue',
            'description': '高周疲劳试验',
            'fields': [
                {'field_name': '循环次数', 'field_code': 'number_of_cycles', 'field_type': 'number', 'unit': '次'},
            ]
        },
        {
            'name': '低周疲劳',
            'code': 'low_cycle_fatigue',
            'description': '低周疲劳试验',
            'fields': [
                {'field_name': '循环次数', 'field_code': 'number_of_cycles', 'field_type': 'number', 'unit': '次'},
            ]
        },
        {
            'name': '旋转弯曲疲劳',
            'code': 'rotary_bending_fatigue',
            'description': '旋转弯曲疲劳试验',
            'fields': [
                {'field_name': '循环次数', 'field_code': 'number_of_cycles', 'field_type': 'number', 'unit': '次'},
            ]
        },
    ]
    
    for cat_data in default_categories:
        existing = session.query(TestCategory).filter_by(code=cat_data['code']).first()
        if not existing:
            category = TestCategory(
                name=cat_data['name'],
                code=cat_data['code'],
                description=cat_data.get('description')
            )
            session.add(category)
            session.flush()
            
            for i, field_data in enumerate(cat_data.get('fields', [])):
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

def init_db(db_path=None, db_url=None):
    """初始化数据库连接
    
    Args:
        db_path: SQLite数据库路径（兼容旧接口）
        db_url: 数据库连接URL（优先使用，支持PostgreSQL）
    """
    if db_url:
        engine = create_engine(db_url, echo=False)
    elif db_path:
        db_url = f'sqlite:///{db_path}'
        engine = create_engine(db_url, echo=False)
    else:
        # 使用默认的PostgreSQL连接
        from config import DATABASE_URL
        engine = create_engine(DATABASE_URL, echo=False)
    
    Base.metadata.create_all(engine)
    return engine


def init_experimental_condition_fields(session):
    """初始化试验条件字段定义"""
    default_fields = [
        {'field_code': 'temperature', 'field_name': '温度', 'field_type': 'text', 'unit': '℃'},
        {'field_code': 'stress', 'field_name': '应力', 'field_type': 'number', 'unit': 'MPa'},
        {'field_code': 'test_time', 'field_name': '试验时间', 'field_type': 'number', 'unit': 'h'},
        {'field_code': 'strain', 'field_name': '应变', 'field_type': 'number', 'unit': '%'},
        {'field_code': 'speed', 'field_name': '速度', 'field_type': 'number', 'unit': 'mm/min'},
        {'field_code': 'other_conditions', 'field_name': '其他条件', 'field_type': 'text', 'unit': None},
    ]
    
    for i, field_data in enumerate(default_fields):
        existing = session.query(ExperimentalConditionField).filter_by(field_code=field_data['field_code']).first()
        if not existing:
            field = ExperimentalConditionField(
                field_code=field_data['field_code'],
                field_name=field_data['field_name'],
                field_type=field_data['field_type'],
                unit=field_data.get('unit'),
                sort_order=i
            )
            session.add(field)
    
    session.commit()


def init_condition_constraints(session):
    """初始化试验条件约束配置"""
    # 获取所有测试类别
    categories = {cat.code: cat.id for cat in session.query(TestCategory).all()}
    
    # 约束配置
    constraints_config = [
        # chemical_composition: 只能填 other_conditions
        {'category_code': 'chemical_composition', 'field_code': 'other_conditions', 'is_required': False, 'is_allowed': True, 'mutually_exclusive_group': None},
        
        # tension: 只能填 temperature（必填）和 other_conditions
        {'category_code': 'tension', 'field_code': 'temperature', 'is_required': True, 'is_allowed': True, 'mutually_exclusive_group': None},
        {'category_code': 'tension', 'field_code': 'other_conditions', 'is_required': False, 'is_allowed': True, 'mutually_exclusive_group': None},
        
        # impact: 只能填 temperature（必填）和 other_conditions
        {'category_code': 'impact', 'field_code': 'temperature', 'is_required': True, 'is_allowed': True, 'mutually_exclusive_group': None},
        {'category_code': 'impact', 'field_code': 'other_conditions', 'is_required': False, 'is_allowed': True, 'mutually_exclusive_group': None},
        
        # stress_rupture: 只能填 temperature、stress、test_time（都必填）和 other_conditions
        {'category_code': 'stress_rupture', 'field_code': 'temperature', 'is_required': True, 'is_allowed': True, 'mutually_exclusive_group': None},
        {'category_code': 'stress_rupture', 'field_code': 'stress', 'is_required': True, 'is_allowed': True, 'mutually_exclusive_group': None},
        {'category_code': 'stress_rupture', 'field_code': 'test_time', 'is_required': True, 'is_allowed': True, 'mutually_exclusive_group': None},
        {'category_code': 'stress_rupture', 'field_code': 'other_conditions', 'is_required': False, 'is_allowed': True, 'mutually_exclusive_group': None},
        
        # creep: 只能填 temperature、stress、test_time（都必填）和 other_conditions
        {'category_code': 'creep', 'field_code': 'temperature', 'is_required': True, 'is_allowed': True, 'mutually_exclusive_group': None},
        {'category_code': 'creep', 'field_code': 'stress', 'is_required': True, 'is_allowed': True, 'mutually_exclusive_group': None},
        {'category_code': 'creep', 'field_code': 'test_time', 'is_required': True, 'is_allowed': True, 'mutually_exclusive_group': None},
        {'category_code': 'creep', 'field_code': 'other_conditions', 'is_required': False, 'is_allowed': True, 'mutually_exclusive_group': None},
        
        # hardness: 只能填 other_conditions
        {'category_code': 'hardness', 'field_code': 'other_conditions', 'is_required': False, 'is_allowed': True, 'mutually_exclusive_group': None},
        
        # fracture_toughness: 只能填 temperature（必填）和 other_conditions
        {'category_code': 'fracture_toughness', 'field_code': 'temperature', 'is_required': True, 'is_allowed': True, 'mutually_exclusive_group': None},
        {'category_code': 'fracture_toughness', 'field_code': 'other_conditions', 'is_required': False, 'is_allowed': True, 'mutually_exclusive_group': None},
        
        # macro_structure: 只能填 other_conditions
        {'category_code': 'macro_structure', 'field_code': 'other_conditions', 'is_required': False, 'is_allowed': True, 'mutually_exclusive_group': None},
        
        # fracture_inspection: 只能填 other_conditions
        {'category_code': 'fracture_inspection', 'field_code': 'other_conditions', 'is_required': False, 'is_allowed': True, 'mutually_exclusive_group': None},
        
        # grain_size: 只能填 other_conditions
        {'category_code': 'grain_size', 'field_code': 'other_conditions', 'is_required': False, 'is_allowed': True, 'mutually_exclusive_group': None},
        
        # non_metallic_inclusion: 只能填 other_conditions
        {'category_code': 'non_metallic_inclusion', 'field_code': 'other_conditions', 'is_required': False, 'is_allowed': True, 'mutually_exclusive_group': None},
        
        # microstructure: 只能填 other_conditions
        {'category_code': 'microstructure', 'field_code': 'other_conditions', 'is_required': False, 'is_allowed': True, 'mutually_exclusive_group': None},
        
        # high_cycle_fatigue: 只能填 temperature（必填）、stress、strain（互斥）、other_conditions
        {'category_code': 'high_cycle_fatigue', 'field_code': 'temperature', 'is_required': True, 'is_allowed': True, 'mutually_exclusive_group': None},
        {'category_code': 'high_cycle_fatigue', 'field_code': 'stress', 'is_required': False, 'is_allowed': True, 'mutually_exclusive_group': 'stress_strain'},
        {'category_code': 'high_cycle_fatigue', 'field_code': 'strain', 'is_required': False, 'is_allowed': True, 'mutually_exclusive_group': 'stress_strain'},
        {'category_code': 'high_cycle_fatigue', 'field_code': 'other_conditions', 'is_required': False, 'is_allowed': True, 'mutually_exclusive_group': None},
        
        # low_cycle_fatigue: 只能填 temperature（必填）、stress、strain（互斥）、other_conditions
        {'category_code': 'low_cycle_fatigue', 'field_code': 'temperature', 'is_required': True, 'is_allowed': True, 'mutually_exclusive_group': None},
        {'category_code': 'low_cycle_fatigue', 'field_code': 'stress', 'is_required': False, 'is_allowed': True, 'mutually_exclusive_group': 'stress_strain'},
        {'category_code': 'low_cycle_fatigue', 'field_code': 'strain', 'is_required': False, 'is_allowed': True, 'mutually_exclusive_group': 'stress_strain'},
        {'category_code': 'low_cycle_fatigue', 'field_code': 'other_conditions', 'is_required': False, 'is_allowed': True, 'mutually_exclusive_group': None},
        
        # rotary_bending_fatigue: 只能填 temperature（必填）、stress（必填）、speed（必填）、other_conditions
        {'category_code': 'rotary_bending_fatigue', 'field_code': 'temperature', 'is_required': True, 'is_allowed': True, 'mutually_exclusive_group': None},
        {'category_code': 'rotary_bending_fatigue', 'field_code': 'stress', 'is_required': True, 'is_allowed': True, 'mutually_exclusive_group': None},
        {'category_code': 'rotary_bending_fatigue', 'field_code': 'speed', 'is_required': True, 'is_allowed': True, 'mutually_exclusive_group': None},
        {'category_code': 'rotary_bending_fatigue', 'field_code': 'other_conditions', 'is_required': False, 'is_allowed': True, 'mutually_exclusive_group': None},
    ]
    
    for config in constraints_config:
        category_id = categories.get(config['category_code'])
        if category_id:
            existing = session.query(ConditionConstraint).filter_by(
                category_id=category_id,
                field_code=config['field_code']
            ).first()
            
            if not existing:
                constraint = ConditionConstraint(
                    category_id=category_id,
                    field_code=config['field_code'],
                    is_required=config['is_required'],
                    is_allowed=config['is_allowed'],
                    mutually_exclusive_group=config.get('mutually_exclusive_group')
                )
                session.add(constraint)
    
    session.commit()


def generate_item_key(field_name: str, user_item_key=None) -> str:
    """
    自动生成 item_key（项目关键字），返回 JSON 数组格式
    
    规则：
    1. 如果用户已提供 item_key（字符串或数组），直接返回 JSON 数组格式
    2. 如果未提供，从 field_name 中提取1-2个关键字，返回 JSON 数组
    
    Args:
        field_name: 字段名称，如"抗拉强度 Rm"、"屈服强度 Rp0.2"等
        user_item_key: 用户提供的 item_key（可以是字符串或列表，可选）
    
    Returns:
        JSON 数组格式的 item_key，如 '["高温", "抗拉"]'
    """
    import json
    
    # 如果用户已提供，处理用户输入
    if user_item_key is not None:
        if isinstance(user_item_key, list):
            # 用户提供的是列表，直接转为 JSON
            return json.dumps(user_item_key, ensure_ascii=False)
        elif isinstance(user_item_key, str) and user_item_key.strip():
            # 用户提供的是字符串，转为单元素数组或逗号分隔的数组
            user_input = user_item_key.strip()
            if ',' in user_input:
                # 逗号分隔的多关键字
                keywords = [kw.strip() for kw in user_input.split(',') if kw.strip()]
                return json.dumps(keywords, ensure_ascii=False)
            else:
                # 单个关键字
                return json.dumps([user_input], ensure_ascii=False)
    
    if not field_name:
        return json.dumps([], ensure_ascii=False)
    
    # 从 field_name 中提取关键字
    keywords = _extract_keywords_from_field_name(field_name)
    
    # 返回 JSON 数组格式
    return json.dumps(keywords, ensure_ascii=False)


def _extract_keywords_from_field_name(field_name: str) -> list:
    """
    从字段名称中提取关键字，返回关键字列表（最多2个）
    
    Args:
        field_name: 字段名称
    
    Returns:
        关键字列表，如 ["高温", "抗拉"]
    """
    keywords = []
    
    # 关键字映射表
    keyword_mapping = {
        # 温度相关
        '高温': '高温',
        '低温': '低温',
        '室温': '室温',
        '常温': '常温',
        '时效': '时效',
        '热处理': '热处理',
        # 强度相关
        '抗拉强度': '抗拉',
        '屈服强度': '屈服',
        '规定塑性延伸强度': '延伸',
        # 塑性相关
        '伸长率': '伸长',
        '断面收缩率': '收缩',
        # 其他
        '冲击吸收能量': '冲击',
        '断裂韧度': '韧度',
        '持久时间': '持久',
        '蠕变': '蠕变',
        '硬度': '硬度',
        '循环次数': '疲劳',
        '宏观组织': '宏观',
        '显微组织': '显微',
    }
    
    # 按优先级检查并提取关键字
    # 1. 先检查温度相关关键字
    temperature_keywords = ['高温', '低温', '室温', '常温', '时效', '热处理']
    for temp_kw in temperature_keywords:
        if temp_kw in field_name:
            keywords.append(temp_kw)
            break
    
    # 2. 检查强度/塑性相关关键字
    strength_keywords = ['抗拉强度', '屈服强度', '规定塑性延伸强度']
    for kw in strength_keywords:
        if kw in field_name:
            mapped = keyword_mapping.get(kw)
            if mapped and mapped not in keywords:
                keywords.append(mapped)
            break
    
    # 3. 检查其他关键字
    other_keywords = {
        '伸长率': '伸长',
        '断面收缩率': '收缩',
        '冲击吸收能量': '冲击',
        '断裂韧度': '韧度',
        '持久时间': '持久',
        '蠕变': '蠕变',
        '硬度': '硬度',
        '循环次数': '疲劳',
        '宏观组织': '宏观',
        '显微组织': '显微',
    }
    
    for kw, mapped in other_keywords.items():
        if kw in field_name:
            if mapped not in keywords:
                keywords.append(mapped)
            break
    
    # 最多返回2个关键字
    return keywords[:2]


def match_item_key(record_item_key: str, search_keyword: str) -> bool:
    """
    匹配 item_key 和搜索关键字
    
    Args:
        record_item_key: 数据库中存储的 item_key（JSON数组格式）
        search_keyword: 用户输入的搜索关键字
    
    Returns:
        是否匹配成功
    """
    import json
    
    if not record_item_key or not search_keyword:
        return False
    
    try:
        # 解析 JSON 数组
        keywords = json.loads(record_item_key)
        if not isinstance(keywords, list):
            return False
        
        # 搜索关键字与数组中任一元素匹配即可
        search_keyword = search_keyword.strip().lower()
        for keyword in keywords:
            if keyword.lower() == search_keyword:
                return True
        return False
    except (json.JSONDecodeError, TypeError):
        # 如果解析失败，尝试直接比较
        return record_item_key.strip().lower() == search_keyword.lower()
