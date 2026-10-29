from fastapi import FastAPI

if __package__:
    from .demo_api import router
else:
    from demo_api import router

app = FastAPI(title="Outsourcing Site API")
app.include_router(router)


@app.middleware("http")
async def demo_no_cache(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/api/demo/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/api/health")
def health():
    return {"status": "ok"}
