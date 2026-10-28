from fastapi import FastAPI

app = FastAPI(title="Outsourcing Site API")


@app.get("/api/health")
def health():
    return {"status": "ok"}
