import os
import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
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
        
    frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../frontend/dist"))
    if os.path.exists(frontend_dir):
        assets_dir = os.path.join(frontend_dir, "assets")
        if os.path.exists(assets_dir):
            app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")
        
        @app.get("/{full_path:path}", include_in_schema=False)
        def serve_spa(full_path: str):
            if full_path.startswith("api/") or full_path.startswith("auth/") or full_path == "health":
                return JSONResponse(status_code=404, content={"detail": "Not Found"})
            
            # Serve specific files in dist root (like vite.svg, etc) if they exist
            requested_file = os.path.join(frontend_dir, full_path)
            if os.path.isfile(requested_file):
                return FileResponse(requested_file)
                
            return FileResponse(os.path.join(frontend_dir, "index.html"))

    return app
