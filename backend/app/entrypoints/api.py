import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pythonjsonlogger import jsonlogger
from ..config import load_settings
from ..wiring import build_container, Container
from ..errors import AppError

def setup_logging():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        
    handler = logging.StreamHandler()
    formatter = jsonlogger.JsonFormatter('%(asctime)s %(levelname)s %(name)s %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

def create_app(container: Container | None = None) -> FastAPI:
    setup_logging()
    
    if container is None:
        container = build_container(load_settings())
        
    app = FastAPI(title="Sports Play Analyzer")
    
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        return JSONResponse(
            status_code=400,
            content={"error": {"code": exc.__class__.__name__, "message": str(exc)}}
        )

    @app.get("/health")
    def health():
        db_ok = container.health_check.check_db()
        status_code = 200 if db_ok else 503
        return JSONResponse(
            status_code=status_code,
            content={
                "status": "ok" if db_ok else "error",
                "db": "ok" if db_ok else "error",
                "version": container.settings.git_sha
            }
        )
        
    return app
