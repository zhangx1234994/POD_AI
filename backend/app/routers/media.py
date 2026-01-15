"""媒体/OSS 相关路由。"""

import jwt
from fastapi import APIRouter, HTTPException, status

from app.schemas import media as schemas
from app.services.oss import oss_service
from app.services.upload_token import upload_token_service

router = APIRouter()


@router.post("/v1/upload-key", response_model=schemas.UploadKeyResponse)
async def issue_upload_key(payload: schemas.UploadKeyRequest) -> schemas.UploadKeyResponse:
    token = upload_token_service.issue_token(user_id=payload.userId)
    return schemas.UploadKeyResponse(**token)


@router.post("/v1/sts", response_model=schemas.OssCredentialResponse)
async def get_sts(payload: schemas.UploadCredentialRequest) -> schemas.OssCredentialResponse:
    try:
        user_id = upload_token_service.verify_token(payload.uploadKey)
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    sts_info = oss_service.generate_upload_credentials(user_id=user_id, file_name=payload.fileName)
    return schemas.OssCredentialResponse(**sts_info)


@router.post("/v1/oss-callback", status_code=status.HTTP_204_NO_CONTENT)
async def oss_callback(payload: schemas.OssCallbackPayload) -> None:
    # TODO: 校验签名、写入 media_objects、触发任务
    _ = payload
    return None


@router.post("/v1/signed-download", response_model=schemas.SignedDownloadResponse)
async def signed_download(payload: schemas.SignedDownloadRequest) -> schemas.SignedDownloadResponse:
    if not payload.objectKey:
        raise HTTPException(status_code=400, detail="objectKey is required")
    url = oss_service.sign_download_url(object_key=payload.objectKey, ttl=payload.ttl)
    return schemas.SignedDownloadResponse(url=url)
