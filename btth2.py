from fastapi import FastAPI, status, Request, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Any, Literal
from fastapi.responses import JSONResponse
from datetime import datetime, date
from fastapi.exceptions import RequestValidationError

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

class BaseResponse(BaseModel):
    status_code: int
    message: str
    data: Optional[Any] | None
    error: Optional[str] | None
    timestamp: str
    path: str

class CreateAssets(BaseModel):
    serial_number: str
    model: str = Field(min_length=2, max_length=255)
    stock_available: int = Field(ge=0)
    status: Literal["READY", "ALLOCATED", "REPAIRING", "SCRAPPED"]

class UpdateAssets(BaseModel):
    serial_number: str
    model: str = Field(min_length=2, max_length=255)
    stock_available: int = Field(ge=0)
    status: Literal["READY", "ALLOCATED", "REPAIRING", "SCRAPPED"]

class CreateAllocations(BaseModel):
    asset_id : int
    employee_email: str = Field(pattern=r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
    allocated_quantity: int = Field(gt=0)
    start_date: date
    duration_months: int = Field(ge=1, le=12)

def create_response(request: Request,
                    status_code: int,
                    message: str,
                    data: Any | None = None,
                    error: str | None = None):
    return BaseResponse(
        status_code= status_code,
        message = message,
        data = data,
        error = error,
        timestamp = datetime.now().isoformat(),
        path = request.url.path
    )

def check_number(number: str):
    for asset in assets:
        if asset["serial_number"] == number:
            raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Mã nhân viên đã tồn tại"
        )

def check_space(info: str):
    if info.strip() == "":
        raise HTTPException(
            status_code=400,
            detail="Thông tin này không được để trống"
        )
    return info

@app.exception_handler(HTTPException)
def http_exception_handler(request: Request, exc: HTTPException):
    response = create_response(request = request, status_code= exc.status_code, message = "Request Failed", error= exc.detail)
    return JSONResponse(status_code=exc.status_code, content=response.model_dump())

@app.exception_handler(RequestValidationError)
def http_exception_handler(request, exc):
    response = create_response(request = request, status_code= 422, message = "Validation Error", error= exc.errors())
    return JSONResponse(status_code=422, content=response.model_dump())

@app.post("/assets", response_model=BaseResponse, status_code= status.HTTP_201_CREATED)
def create_assets(data: CreateAssets, request: Request):
    data.serial_number = check_space(data.serial_number).strip()
    check_number(data.serial_number)
    data.model = check_space(data.model).strip()
    new_asset = {
        "id" : max(asset["id"] for asset in assets)+1,
        "serial_number": data.serial_number,
        "model": data.model,
        "stock_available": data.stock_available,
        "status": data.status
    }
    assets.append(new_asset)
    return create_response(request, status.HTTP_201_CREATED, "Thêm thành công tài sản thiết bị mới", new_asset)

@app.get("/assets", response_model=BaseResponse, status_code= status.HTTP_200_OK)
def get_assets(request: Request, keyword: str | None = None, status_input: Literal["READY", "ALLOCATED", "REPAIRING", "SCRAPPED"] | None = None, min_stock: int | None = None):
    result = assets
    if keyword:
        result = [asset for asset in result if keyword.lower().strip() in asset["serial_number"].strip().lower() or keyword.lower().strip() in asset["model"].strip().lower()]
    if status_input:
        result = [asset for asset in result if status_input == asset["status"]]
    if min_stock is not None:
        result = [asset for asset in result if asset["stock_available"] >= min_stock]
    return create_response(request, status.HTTP_200_OK, "Danh sách tài sản thiết bị", result)

@app.get("/assets/{asset_id}", response_model=BaseResponse, status_code= status.HTTP_200_OK)
def get_asset_by_id(request: Request, asset_id: int):
    asset = next((asset for asset in assets if asset["id"] == asset_id), None)
    if asset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset is not found"
        )
    return create_response(request, status.HTTP_200_OK, "Lấy thành công tài sản thiết bị", asset)

@app.put("/assets/{asset_id}", response_model=BaseResponse, status_code= status.HTTP_200_OK)
def update_asset(request: Request, asset_id: int, data: UpdateAssets):
    data.serial_number = check_space(data.serial_number).strip()
    check_number(data.serial_number)
    data.model = check_space(data.model).strip()
    asset = next((asset for asset in assets if asset["id"] == asset_id), None)
    duplicate = next((asset for asset in assets if asset["serial_number"] == data.serial_number and asset["id"] != asset_id),None)

    if duplicate:
        raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Serial number already exists"
    )
    asset["serial_number"] = data.serial_number
    asset["model"] = data.model
    asset["stock_available"] = data.stock_available
    asset["status"] = data.status
    return create_response(request, status.HTTP_200_OK, "Đã cập nhật thành công", asset)

@app.delete("/assets/{asset_id}", response_model=BaseResponse, status_code= status.HTTP_200_OK)
def delete_asset(request: Request, asset_id: int):
    for i, asset in enumerate(assets):
        if asset["id"] == asset_id:
            assets.pop(i)
            return create_response(request, status.HTTP_200_OK, "Xóa thành công tài sản thiết bị", asset)
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Asset is not found"
    )
    
@app.post("/allocations", response_model=BaseResponse, status_code= status.HTTP_201_CREATED)
def create_allocation(request: Request, data: CreateAllocations):
    data.serial_number = check_space(data.serial_number).strip()
    check_number(data.serial_number)
    asset = next((asset for asset in assets if asset["id"] == data.asset_id), None)
    data.model = check_space(data.model).strip()
    if asset["status"] != "READY":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Asset is not Ready"
    )
    if asset["stock_available"] < data.allocated_quantity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Số lượng thiết bị yêu cầu cấp phát không được phép vượt quá số lượng tồn kho khả dụng thực tế của tài sản đó"
    )
    asset["stock_available"] -= data.allocated_quantity  
    new_allocation = {
        "id": max(allocation["id"] for allocation in allocations)+1,
        "asset_id": data.asset_id,
        "employee_email": data.employee_email,
        "allocated_quantity": data.allocated_quantity,
        "start_date": data.start_date,
        "duration_months": data.duration_months
    }
    allocations.append(new_allocation)
    return create_response(request, status.HTTP_201_CREATED, "Đăng ký cấp phát thiết bị thành công", new_allocation)

@app.get("/allocations", response_model=BaseResponse, status_code= status.HTTP_200_OK)
def get_allocations(request: Request):
    if not allocations:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Allocations is not Exist"
        )
    return create_response(request, status.HTTP_200_OK, "Danh sách đăng ký thiết bị cấp phát", allocations)