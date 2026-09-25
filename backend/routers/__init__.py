from .patients import router as patients_router
from .studies import router as studies_router
from .series import router as series_router
from .instances import router as instances_router
from .upload import router as upload_router
from .denoising import router as denoising_router
from .auth import router as auth_router, get_current_user

__all__ = [
    "patients_router",
    "studies_router",
    "series_router",
    "instances_router",
    "upload_router",
    "denoising_router",
    "auth_router",
    "get_current_user"
]
