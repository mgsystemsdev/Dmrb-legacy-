from __future__ import annotations
import asyncio
import concurrent.futures
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from api.schemas.imports import UploadResponse, BatchStatusResponse
from api.deps import get_current_user
from services import import_service

router = APIRouter()

@router.post("/imports/upload", response_model=UploadResponse)
async def upload_import(
    property_id: int = Form(...),
    report_type: str = Form(...),
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user)
):
    content = await file.read()
    
    # Run in a thread pool with a timeout guard
    loop = asyncio.get_running_loop()
    with concurrent.futures.ThreadPoolExecutor() as pool:
        try:
            # We use wait() to implement the timeout on the future
            future = loop.run_in_executor(
                pool, 
                import_service.run_import_pipeline,
                property_id,
                report_type,
                content,
                file.filename
            )
            # Wait up to 60 seconds
            result = await asyncio.wait_for(future, timeout=60.0)
            
            # orchestrator result mapping to UploadResponse
            return UploadResponse(
                batch_id=result.get("batch_id"),
                status=result.get("status"),
                checksum=result.get("checksum"),
                diagnostics=result.get("diagnostics", [])
            )
        except asyncio.TimeoutError:
            # If it timeouts, we might not have the batch_id yet if it hasn't reached that point
            # But run_import_pipeline does start_batch early.
            # Actually, the requirement says "Return the existing import_batch.batch_id"
            # If it's still running, we can try to find it by checksum.
            checksum = import_service.compute_checksum(content)
            existing = import_service.get_existing_batch(property_id, report_type, checksum)
            
            return UploadResponse(
                batch_id=existing["batch_id"] if existing else None,
                status="PROCESSING",
                checksum=checksum,
                diagnostics=["Import is taking longer than 60s, processing continues in background."]
            )
        except Exception as exc:
            # Re-read checksum for failed response
            checksum = import_service.compute_checksum(content)
            return UploadResponse(
                batch_id=None,
                status="FAILED",
                checksum=checksum,
                diagnostics=[f"Import failed: {str(exc)}"]
            )

@router.get("/imports/{batch_id}/status", response_model=BatchStatusResponse)
async def get_import_status(
    batch_id: int,
    user: dict = Depends(get_current_user)
):
    detail = import_service.get_batch_detail(batch_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Batch not found")
        
    return BatchStatusResponse(
        batch_id=detail["batch_id"],
        property_id=detail["property_id"],
        report_type=detail["report_type"],
        status=detail["status"],
        record_count=detail["record_count"],
        created_at=detail["created_at"],
        updated_at=detail["updated_at"],
        summary=detail.get("summary")
    )
