from fastapi import FastAPI, HTTPException, Request, status
from pydantic import BaseModel, Field
from typing import Literal
from fastapi.responses import JSONResponse
from datetime import date, datetime

app = FastAPI()

assets = [
    {"id": 1, "serial_number": "SN-MAC-01", "model": "MacBook Pro M3", "stock_available": 5, "status": "READY"},
    {"id": 2, "serial_number": "SN-DELL-02", "model": "Dell UltraSharp 27", "stock_available": 10, "status": "READY"},
    {"id": 3, "serial_number": "SN-THINK-03", "model": "ThinkPad X1 Carbon", "stock_available": 0, "status": "REPAIRING"}
]

allocations = [
    {
        "id": 1,
        "asset_id": 1,
        "employee_email": "dev.nguyen@company.com",
        "allocated_quantity": 1,
        "start_date": "2026-07-01",
        "duration_months": 12
    }
]

class Assets(BaseModel):
    serial_number: str
    model: str = Field(min_length=2, max_length=255)
    stock_available: int = Field(ge=0)
    status: Literal["READY", "ALLOCATED", "REPAIRING", "SCRAPPED"]

class Allocations(BaseModel):
    asset_id : int
    employee_email: str = Field(pattern=r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
    allocated_quantity: int = Field(gt=0)
    start_date: date
    duration_months: int = Field(ge=1, le=12)

def get_asset_by_id(asset_id: int):
    for asset in assets:
        if asset["id"] == asset_id:
            return asset
    return None

def check_number(number: str):
    for asset in assets:
        if asset["serial_number"] == number:
            raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Serial number đã tồn tại"
        )

def check_space(info: str):
    if info.strip() == "":
        raise HTTPException(
            status_code=400,
            detail="Thông tin này không được để trống"
        )
    return info

def success_response(request: Request, message: str, data=None, status_code=200):
    return JSONResponse(
        status_code=status_code,
        content={
            "status_code": status_code,
            "message": message,
            "data": data,
            "error": None,
            "path": request.url.path
        }
    )


@app.exception_handler(HTTPException)
def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status_code": exc.status_code,
            "message": "Request failed",
            "new_info": None,
            "error": exc.detail,
            "timestamp": datetime.now().isoformat(),
            "path": request.url.path
        }
    )


@app.post("/assets", status_code=status.HTTP_201_CREATED)
def create_asset(request: Request, new_asset: Assets):
    new_asset.serial_number = check_space(new_asset.serial_number).strip()
    check_number(new_asset.serial_number)
    new_asset.model = check_space(new_asset.model).strip()
    assets.append({
        "id": max(asset["id"] for asset in assets)+1,
        "serial_number": new_asset.serial_number,
        "model": new_asset.model,
        "stock_available": new_asset.stock_available,
        "status": new_asset.status
    })
    return success_response(
        request = request,
        status_code=201,
        message= "Thêm tài sản thiết bị mới thành công",
        new_info=assets
    )


@app.get("/assets")
def get_assets(keyword: str | None = None, status: Literal["READY", "ALLOCATED", "REPAIRING", "SCRAPPED"] | None = None, min_weight: int | None = None):
    if not assets:
        return {"message": "Danh sách tài sản thiết bị đang trống"}
    result = assets
    if keyword:
        result = [asset for asset in result if keyword.strip().lower() in asset['code'].strip().lower()
                  or keyword.strip().lower() in asset['model'].strip().lower()]
    if status:
        result = [asset for asset in result if status.strip().upper() == asset['status']]
    if min_weight:
        result = [asset for asset in result if asset['stock_available'] >= min_weight]
    if not result:
        raise HTTPException(
            status_code=404,
            detail="Asset not found"
        )
    return result

@app.get("/assets/{asset_id}")
def get_asset(asset_id: int):
    for asset in assets:
        if asset["id"] == asset_id:
            return asset
    raise HTTPException(
        status_code=404,
        detail="Asset not found"
    )

@app.put("/assets/{asset_id}")
def update_asset(request: Request, asset_id: int, new_info: Assets):
    new_info.serial_number = check_space(new_info.serial_number).strip()
    duplicate = next((asset for asset in assets if asset["serial_number"] == new_info.serial_number and asset["id"] != asset_id),None)
    if duplicate:
        raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Serial number đã tồn tại"
    )
    new_info.model = check_space(new_info.model).strip()
    found = get_asset_by_id(asset_id)
    if not found:
        raise HTTPException(
        status_code=404,
        detail="Asset not found"
    )
    found['serial_number']= new_info.serial_number
    found['model']= new_info.model
    found['stock_available']= new_info.stock_available
    found['status']= new_info.status
    return success_response(
        request=request,
        status_code=200,
        message="Cập nhật thành công",
        new_info=found
    )

@app.delete("/assets/{asset_id}")
def delete_asset(request: Request, asset_id: int):
    found = get_asset_by_id(asset_id)
    if not found:
        raise HTTPException(
            status_code=404,
            detail="Asset not found"
        )
    assets.remove(found)
    return success_response(
        request=request,
        status_code=200,
        message="Xóa thành công",
        new_info = found
    )


@app.post("/allocations", status_code=status.HTTP_201_CREATED)
def add_allocation(request: Request, new_allocation: Allocations):
    asset = get_asset_by_id(new_allocation.asset_id)
    if not asset:
        raise HTTPException(
            status_code=404,
            detail="Asset not found"
        )

    if asset["status"] != "READY":
        raise HTTPException(
            status_code=400,
            detail="Asset is not ready"
        )

    if new_allocation.allocated_quantity > asset["stock_available"]:
        raise HTTPException(
            status_code=400,
            detail="Số lượng thiết bị yêu cầu cấp phát không được phép vượt quá số lượng tồn kho khả dụng thực tế của tài sản đó"
        )

    asset["stock_available"] -= new_allocation.allocated_quantity

    allocations.append({
        "id": max(allocation["id"] for allocation in allocations) + 1,
        "asset_id": new_allocation.asset_id,
        "employee_email": new_allocation.employee_email,
        "allocated_quantity": new_allocation.allocated_quantity,
        "start_date": new_allocation.start_date.isoformat(),
        "duration_months": new_allocation.duration_months
    })

    return success_response(
        request=request,
        status_code=201,
        message="Device allocated successfully",
        data=allocations
    )
    

@app.get("/allocations")
def get_allocations():
    if not allocations:
        return {"message": "Danh sách cấp phát thiết bị hiện đang trống"}
    return allocations
