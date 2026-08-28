from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .api import chapters, ideas, projects, volumes
from .database import Base, engine

Base.metadata.create_all(bind=engine)

app = FastAPI(title="小说创作智能体")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects.router, prefix="/api", tags=["projects"])
app.include_router(chapters.router, prefix="/api", tags=["chapters"])
app.include_router(volumes.router, prefix="/api", tags=["volumes"])
app.include_router(ideas.router, prefix="/api", tags=["ideas"])


@app.get("/api/health")
def health():
    return {"status": "ok"}


# 托管前端静态文件（若存在）
FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"
if (FRONTEND_DIR / "index.html").exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn

    # 注意：须在 backend 目录下以模块方式运行：python -m app.main
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
