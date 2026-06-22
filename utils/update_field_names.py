"""
更新现有数据库中的字段名称
将拉伸类别的字段名称更新为带下标的格式
"""
import sqlite3
import os

DB_PATH = '/home/yb/material_spec_db/material_specs.db'

def update_field_names():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 更新拉伸类别的字段名称
    updates = [
        ('yield_strength', 'Rp<sub>0.2</sub>'),
        ('proof_strength', 'Rp<sub>1.0</sub>'),
        ('upper_yield_strength', 'ReH'),
        ('lower_yield_strength', 'ReL'),
    ]
    
    for field_code, new_name in updates:
        cursor.execute("""
            UPDATE test_field_definitions 
            SET field_name = ? 
            WHERE field_code = ?
        """, (new_name, field_code))
        print(f"更新 {field_code} -> {new_name}")
    
    conn.commit()
    conn.close()
    print("更新完成！")

if __name__ == '__main__':
    update_field_names()
