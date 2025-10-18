from fastapi import FastAPI
from app.api.v1.health import router as health_router
from app.api.v1.user import router as user_router
from app.api.v1.transaction import router as transaction_router
from app.api.v1.sync import router as sync_router

app = FastAPI(title="OfflinePay Backend")

app.include_router(user_router)
app.include_router(transaction_router)
app.include_router(sync_router)
app.include_router(health_router)



