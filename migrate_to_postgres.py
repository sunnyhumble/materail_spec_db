#!/usr/bin/env python3
"""
数据库迁移脚本：将SQLite数据库迁移到PostgreSQL
使用前请确保已创建PostgreSQL数据库和用户
"""

import sqlite3
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
import sys
import os
from datetime import datetime

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import DATABASE_PATH, DATABASE_URL
from database.models import Base, TestCategory, TestFieldDefinition, MaterialSpec, TestValue, \
    ExperimentalConditionField, ConditionConstraint, FieldMapping

def get_sqlite_connection(db_path):
    """连接到SQLite数据库"""
    return sqlite3.connect(db_path)

def get_postgres_engine(db_url):
    """创建PostgreSQL引擎"""
    return create_engine(db_url, echo=False)

def table_exists(engine, table_name):
    """检查表是否存在"""
    inspector = inspect(engine)
    return table_name in inspector.get_table_names()

def get_table_data(conn, table_name):
    """获取SQLite表的所有数据"""
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM {table_name}")
    columns = [desc[0] for desc in cursor.description]
    rows = cursor.fetchall()
    return columns, rows

def migrate_test_categories(sqlite_conn, postgres_session):
    """迁移测试类别表"""
    print("迁移测试类别表...")
    columns, rows = get_table_data(sqlite_conn, 'test_categories')
    
    for row in rows:
        data = dict(zip(columns, row))
        # 跳过SQLite的rowid
        data.pop('rowid', None)
        
        # 转换日期字符串
        if data.get('created_at'):
            data['created_at'] = datetime.fromisoformat(data['created_at'].replace('Z', '+00:00'))
        
        category = TestCategory(**data)
        postgres_session.add(category)
    
    postgres_session.commit()
    print(f"  ✓ 迁移了 {len(rows)} 条测试类别")

def migrate_test_field_definitions(sqlite_conn, postgres_session):
    """迁移测试字段定义表"""
    print("迁移测试字段定义表...")
    columns, rows = get_table_data(sqlite_conn, 'test_field_definitions')
    
    for row in rows:
        data = dict(zip(columns, row))
        data.pop('rowid', None)
        
        field_def = TestFieldDefinition(**data)
        postgres_session.add(field_def)
    
    postgres_session.commit()
    print(f"  ✓ 迁移了 {len(rows)} 条字段定义")

def migrate_material_specs(sqlite_conn, postgres_session):
    """迁移材料规范表"""
    print("迁移材料规范表...")
    columns, rows = get_table_data(sqlite_conn, 'material_specs')
    
    for row in rows:
        data = dict(zip(columns, row))
        data.pop('rowid', None)
        
        # 转换日期
        if data.get('created_at'):
            data['created_at'] = datetime.fromisoformat(data['created_at'].replace('Z', '+00:00'))
        if data.get('updated_at'):
            data['updated_at'] = datetime.fromisoformat(data['updated_at'].replace('Z', '+00:00'))
        
        spec = MaterialSpec(**data)
        postgres_session.add(spec)
    
    postgres_session.commit()
    print(f"  ✓ 迁移了 {len(rows)} 条材料规范")

def migrate_test_values(sqlite_conn, postgres_session):
    """迁移测试值表"""
    print("迁移测试值表...")
    columns, rows = get_table_data(sqlite_conn, 'test_values')
    
    for row in rows:
        data = dict(zip(columns, row))
        data.pop('rowid', None)
        
        test_value = TestValue(**data)
        postgres_session.add(test_value)
    
    postgres_session.commit()
    print(f"  ✓ 迁移了 {len(rows)} 条测试值")

def migrate_experimental_condition_fields(sqlite_conn, postgres_session):
    """迁移试验条件字段表"""
    print("迁移试验条件字段表...")
    
    if not table_exists(postgres_session.get_bind(), 'experimental_condition_fields'):
        print("  ⚠ 表 experimental_condition_fields 不存在，跳过")
        return
    
    columns, rows = get_table_data(sqlite_conn, 'experimental_condition_fields')
    
    for row in rows:
        data = dict(zip(columns, row))
        data.pop('rowid', None)
        
        field = ExperimentalConditionField(**data)
        postgres_session.add(field)
    
    postgres_session.commit()
    print(f"  ✓ 迁移了 {len(rows)} 条试验条件字段")

def migrate_condition_constraints(sqlite_conn, postgres_session):
    """迁移条件约束表"""
    print("迁移条件约束表...")
    
    if not table_exists(postgres_session.get_bind(), 'condition_constraints'):
        print("  ⚠ 表 condition_constraints 不存在，跳过")
        return
    
    columns, rows = get_table_data(sqlite_conn, 'condition_constraints')
    
    for row in rows:
        data = dict(zip(columns, row))
        data.pop('rowid', None)
        
        constraint = ConditionConstraint(**data)
        postgres_session.add(constraint)
    
    postgres_session.commit()
    print(f"  ✓ 迁移了 {len(rows)} 条条件约束")

def migrate_field_mappings(sqlite_conn, postgres_session):
    """迁移字段映射表"""
    print("迁移字段映射表...")
    columns, rows = get_table_data(sqlite_conn, 'field_mappings')
    
    for row in rows:
        data = dict(zip(columns, row))
        data.pop('rowid', None)
        
        # 转换日期
        if data.get('created_at'):
            data['created_at'] = datetime.fromisoformat(data['created_at'].replace('Z', '+00:00'))
        
        mapping = FieldMapping(**data)
        postgres_session.add(mapping)
    
    postgres_session.commit()
    print(f"  ✓ 迁移了 {len(rows)} 条字段映射")

def main():
    """主函数"""
    print("=" * 60)
    print("数据库迁移工具：SQLite -> PostgreSQL")
    print("=" * 60)
    
    # 连接到SQLite
    print(f"\n[1] 连接SQLite数据库: {DATABASE_PATH}")
    sqlite_conn = get_sqlite_connection(DATABASE_PATH)
    
    # 列出所有表
    cursor = sqlite_conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cursor.fetchall()]
    print(f"    找到 {len(tables)} 个表: {', '.join(tables)}")
    
    # 连接到PostgreSQL
    print(f"\n[2] 连接PostgreSQL数据库: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else 'localhost'}")
    postgres_engine = get_postgres_engine(DATABASE_URL)
    
    # 创建所有表
    print("\n[3] 创建数据库表结构...")
    Base.metadata.create_all(postgres_engine)
    print("    ✓ 表结构创建完成")
    
    # 创建会话
    PostgresSession = sessionmaker(bind=postgres_engine)
    postgres_session = PostgresSession()
    
    try:
        # 按顺序迁移数据
        print("\n[4] 开始迁移数据...")
        print("-" * 60)
        
        migrate_test_categories(sqlite_conn, postgres_session)
        migrate_test_field_definitions(sqlite_conn, postgres_session)
        migrate_material_specs(sqlite_conn, postgres_session)
        migrate_test_values(sqlite_conn, postgres_session)
        migrate_experimental_condition_fields(sqlite_conn, postgres_session)
        migrate_condition_constraints(sqlite_conn, postgres_session)
        migrate_field_mappings(sqlite_conn, postgres_session)
        
        print("-" * 60)
        print("\n[5] 验证迁移结果...")
        
        # 验证数据
        for table_name in ['test_categories', 'material_specs', 'test_values']:
            count = postgres_session.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar()
            print(f"    {table_name}: {count} 条记录")
        
        print("\n" + "=" * 60)
        print("✓ 迁移完成！")
        print("=" * 60)
        print("\n注意：")
        print("1. 请在PostgreSQL中验证数据完整性")
        print("2. 确认应用配置正确后再切换生产环境")
        print("3. 保留SQLite备份文件以便回滚")
        
    except Exception as e:
        print(f"\n✗ 迁移失败: {e}")
        postgres_session.rollback()
        raise
    finally:
        sqlite_conn.close()
        postgres_session.close()
        postgres_engine.dispose()

if __name__ == '__main__':
    main()
