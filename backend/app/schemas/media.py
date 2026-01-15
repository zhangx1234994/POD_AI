from pydantic import BaseModel, Field


class UploadKeyRequest(BaseModel):
    userId: str = Field(..., min_length=1, max_length=128)


class UploadKeyResponse(BaseModel):
    uploadKey: str
    expiresAt: str
    expiresIn: int


class UploadCredentialRequest(BaseModel):
    uploadKey: str = Field(..., description="前端持有的上传密钥")
    taskId: str
    action: str
    fileName: str
    mimeType: str
    fileSize: int
    channel: str | None = None


class OssCredentials(BaseModel):
    accessKeyId: str
    accessKeySecret: str
    securityToken: str | None = None
    endpoint: str
    publicDomain: str
    bucket: str
    region: str
    expiration: int
    isTemporary: bool
    rootPrefix: str


class OssCredentialResponse(BaseModel):
    ossCredentials: OssCredentials
    objectKey: str
    host: str


class OssMeta(BaseModel):
    taskId: str
    action: str
    userId: str | None = None


class OssCallbackPayload(BaseModel):
    bucket: str
    object: str
    size: int
    mimeType: str
    meta: OssMeta


class SignedDownloadRequest(BaseModel):
    objectKey: str
    ttl: int = Field(300, ge=60, le=3600)


class SignedDownloadResponse(BaseModel):
    url: str
