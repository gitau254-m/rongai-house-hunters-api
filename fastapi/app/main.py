from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import houses,auth, caretakers, appointments, admin
from starlette.middleware.sessions import SessionMiddleware
from app.core.config import settings   # ← ADD THIS LINE
app = FastAPI(
    title="Rongai House Hunters API",
    description="Backend API for the Rongai House Hunters platform",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)
app.add_middleware(SessionMiddleware, secret_key=settings.secret_key)
# CORS lets your Next.js frontend talk to this API.
# Without it, the browser blocks the request.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://rongai-house-finder.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register the houses router.
# Now GET /houses/ is a real endpoint.
app.include_router(houses.router)
app.include_router(auth.router)
app.include_router(caretakers.router)
app.include_router(appointments.router)
app.include_router(admin.router)
@app.get("/health", tags=["System"])
async def health_check():
    return {"status": "ok", "app": "Rongai House Hunters API"}

@app.get("/", tags=["System"])
async def root():
    return {"message": "RHH API is running. Visit /docs to explore."}