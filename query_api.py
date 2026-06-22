"""
材料规范数据查询API服务
使用FastAPI提供RESTful接口查询材料规范数据
端口: 8005
"""

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.operations import MaterialDatabase
from config import DATABASE_PATH

app = FastAPI(
    title="材料规范数据查询API",
    description="提供材料规范数据的查询接口，支持按编号、牌号、状态、类别、取样方向等条件查询",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

db = MaterialDatabase(DATABASE_PATH)


class QueryRequest(BaseModel):
    material_spec_number: Optional[str] = Field(None, description="标准号/编号，精确匹配")
    alloy_grade: Optional[str] = Field(None, description="牌号，支持模糊匹配")
    status: Optional[str] = Field(None, description="状态，支持模糊匹配")
    specification: Optional[str] = Field(None, description="规格，精确匹配")
    sampling_direction: Optional[str] = Field(None, description="取样方向，精确匹配")
    test_category_code: Optional[str] = Field(None, description="测试类别代码，如 tension, impact, chemical_composition")
    experimental_conditions: Optional[Dict[str, Any]] = Field(None, description="试验条件，JSON格式，用于精确匹配试验条件")


class MaterialSpecRequest(BaseModel):
    material_spec_number: str = Field(..., description="标准号/编号")
    alloy_grade: str = Field(..., description="牌号")
    status: str = Field(..., description="状态")
    specification: str = Field(..., description="规格")
    sampling_direction: str = Field(..., description="取样方向")
    test_category_code: str = Field(..., description="测试类别代码")
    additional_conditions: Optional[Dict[str, Any]] = Field(default_factory=dict, description="附加条件")
    remarks: Optional[str] = Field(None, description="备注")
    test_values: List[Dict[str, Any]] = Field(..., description="测试值列表")


class QueryResponse(BaseModel):
    success: bool
    query: Dict[str, Any]
    total: int
    data: List[Dict[str, Any]]


@app.get("/", tags=["首页"])
async def root():
    return {
        "service": "材料规范数据查询API",
        "version": "1.0.0",
        "endpoints": {
            "查询数据": "/query",
            "获取类别": "/categories",
            "获取牌号列表": "/alloy-grades",
            "获取编号列表": "/spec-numbers",
            "健康检查": "/health"
        }
    }


@app.get("/health", tags=["系统"])
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.get("/categories", tags=["基础数据"])
async def get_categories():
    try:
        categories = db.get_test_categories()
        return {"success": True, "data": categories}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/alloy-grades", tags=["基础数据"])
async def get_alloy_grades():
    try:
        grades = db.get_all_alloy_grades()
        return {"success": True, "data": grades, "total": len(grades)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/spec-numbers", tags=["基础数据"])
async def get_spec_numbers():
    try:
        numbers = db.get_all_spec_numbers()
        return {"success": True, "data": numbers, "total": len(numbers)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/query", response_model=QueryResponse, tags=["数据查询"])
async def query_specs(
    material_spec_number: Optional[str] = Query(None, description="标准号/编号，精确匹配"),
    alloy_grade: Optional[str] = Query(None, description="牌号，支持模糊匹配"),
    status: Optional[str] = Query(None, description="状态，支持模糊匹配"),
    specification: Optional[str] = Query(None, description="规格，精确匹配"),
    sampling_direction: Optional[str] = Query(None, description="取样方向，精确匹配"),
    test_category_code: Optional[str] = Query(None, description="测试类别代码")
):
    """
    查询材料规范数据

    支持以下查询条件（全部为可选，传空表示不过滤）：
    - material_spec_number: 标准号，精确匹配
    - alloy_grade: 牌号，模糊匹配
    - status: 状态，模糊匹配
    - specification: 规格，精确匹配
    - sampling_direction: 取样方向，精确匹配
    - test_category_code: 测试类别代码（如 tension, impact, chemical_composition）
    """
    query_params = {
        "material_spec_number": material_spec_number,
        "alloy_grade": alloy_grade,
        "status": status,
        "specification": specification,
        "sampling_direction": sampling_direction,
        "test_category_code": test_category_code
    }

    active_filters = {k: v for k, v in query_params.items() if v}

    try:
        results = db.query_specs(**active_filters)

        return QueryResponse(
            success=True,
            query={
                "filters": active_filters,
                "applied_filters_count": len(active_filters),
                "timestamp": datetime.now().isoformat()
            },
            total=len(results),
            data=results
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/query", response_model=QueryResponse, tags=["数据查询"])
async def query_specs_post(request: QueryRequest):
    """
    POST方式查询材料规范数据

    请求体为JSON，包含查询条件
    """
    query_params = request.model_dump(exclude_none=True)

    try:
        results = db.query_specs(**query_params)

        return QueryResponse(
            success=True,
            query={
                "filters": query_params,
                "applied_filters_count": len(query_params),
                "timestamp": datetime.now().isoformat()
            },
            total=len(results),
            data=results
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 新增 RESTful API 路由 /api/v1/material-specs
@app.get("/api/v1/material-specs", response_model=QueryResponse, tags=["RESTful API"])
async def query_material_specs(
    material_spec_number: Optional[str] = Query(None, description="标准号/编号，精确匹配"),
    alloy_grade: Optional[str] = Query(None, description="牌号，支持模糊匹配"),
    status: Optional[str] = Query(None, description="状态，支持模糊匹配"),
    specification: Optional[str] = Query(None, description="规格，精确匹配"),
    sampling_direction: Optional[str] = Query(None, description="取样方向，精确匹配"),
    test_category_code: Optional[str] = Query(None, description="测试类别代码"),
    temperature: Optional[str] = Query(None, description="试验温度（experimental_conditions中的temperature）")
):
    """
    查询材料规范数据（RESTful风格）

    支持以下查询条件（全部为可选，传空表示不过滤）：
    - material_spec_number: 标准号，精确匹配
    - alloy_grade: 牌号，模糊匹配
    - status: 状态，模糊匹配
    - specification: 规格，精确匹配
    - sampling_direction: 取样方向，精确匹配
    - test_category_code: 测试类别代码
    - temperature: 试验温度（experimental_conditions中的temperature）
    """
    query_params = {
        "material_spec_number": material_spec_number,
        "alloy_grade": alloy_grade,
        "status": status,
        "specification": specification,
        "sampling_direction": sampling_direction,
        "test_category_code": test_category_code
    }
    
    # 处理 experimental_conditions
    experimental_conditions = {}
    if temperature:
        experimental_conditions["temperature"] = temperature
    
    if experimental_conditions:
        query_params["experimental_conditions"] = experimental_conditions

    active_filters = {k: v for k, v in query_params.items() if v}

    try:
        results = db.query_specs(**active_filters)

        return QueryResponse(
            success=True,
            query={
                "filters": active_filters,
                "applied_filters_count": len(active_filters),
                "timestamp": datetime.now().isoformat()
            },
            total=len(results),
            data=results
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/material-specs", tags=["RESTful API"])
async def create_material_spec(request: MaterialSpecRequest):
    """
    创建新的材料规范数据（RESTful风格）

    请求体示例：
    ```json
    {
        "material_spec_number": "GJB 1234-2023",
        "alloy_grade": "30Si2MnCrMoVE",
        "status": "正火+淬火+回火",
        "specification": "棒材",
        "sampling_direction": "纵向",
        "test_category_code": "tension",
        "additional_conditions": {},
        "remarks": "",
        "test_values": [
            {
                "test_category_code": "tension",
                "experimental_conditions": {
                    "temperature": "室温"
                },
                "values": [
                    {
                        "field_code": "tensile_strength",
                        "min_value": "1620",
                        "max_value": "1780",
                        "comparison": "≥",
                        "unit": "MPa"
                    }
                ]
            }
        ]
    }
    ```
    """
    try:
        # 转换请求格式为数据库格式
        spec_data = {
            "material_spec_number": request.material_spec_number,
            "alloy_grade": request.alloy_grade,
            "status": request.status,
            "specification": request.specification,
            "sampling_direction": request.sampling_direction,
            "test_category_code": request.test_category_code,
            "additional_conditions": request.additional_conditions or {},
            "remarks": request.remarks or "",
            "test_values": request.test_values
        }
        
        spec_id = db.add_spec(spec_data)
        return {
            "success": True,
            "id": spec_id,
            "message": "材料规范数据创建成功"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/v1/material-specs/{spec_id}", tags=["RESTful API"])
async def get_material_spec(spec_id: int):
    """
    获取单条材料规范数据（RESTful风格）
    """
    try:
        specs = db.query_specs()
        spec = next((s for s in specs if s['id'] == spec_id), None)
        if spec:
            return {"success": True, "data": spec}
        return {"success": False, "error": "规范不存在"}, 404
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/v1/material-specs/{spec_id}", tags=["RESTful API"])
async def update_material_spec(spec_id: int, request: MaterialSpecRequest):
    """
    更新材料规范数据（RESTful风格）
    """
    try:
        spec_data = {
            "material_spec_number": request.material_spec_number,
            "alloy_grade": request.alloy_grade,
            "status": request.status,
            "specification": request.specification,
            "sampling_direction": request.sampling_direction,
            "test_category_code": request.test_category_code,
            "additional_conditions": request.additional_conditions or {},
            "remarks": request.remarks or "",
            "test_values": request.test_values
        }
        
        db.update_spec(spec_id, spec_data)
        return {"success": True, "message": "材料规范数据更新成功"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/v1/material-specs/{spec_id}", tags=["RESTful API"])
async def delete_material_spec(spec_id: int):
    """
    删除材料规范数据（RESTful风格）
    """
    try:
        db.delete_spec(spec_id)
        return {"success": True, "message": "材料规范数据删除成功"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    print(f"启动材料规范数据查询API服务...")
    print(f"访问地址: http://0.0.0.0:8005")
    print(f"API文档: http://0.0.0.0:8005/docs")
    uvicorn.run(app, host="0.0.0.0", port=8005)
