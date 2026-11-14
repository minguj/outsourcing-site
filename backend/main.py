from fastapi import FastAPI

if __package__:
    from .demo_api import router
    from .nurse_demo import router as nurse_router
    from .site_api import router as site_router
    from .zeb.router import router as zeb_router
else:
    from demo_api import router
    from nurse_demo import router as nurse_router
    from site_api import router as site_router
    from zeb.router import router as zeb_router

app = FastAPI(title="Outsourcing Site API")
app.include_router(router)
app.include_router(site_router)
app.include_router(zeb_router)
app.include_router(nurse_router)


@app.middleware("http")
async def demo_no_cache(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith(("/api/demo/", "/api/admin/", "/api/quotes/", "/api/consult/")):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/api/health")
def health():
    return {"status": "ok"}
