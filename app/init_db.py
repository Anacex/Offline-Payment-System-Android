from app.db import engine
from app.models.base import Base
from app.models.user import User
from app.models.transaction import Transaction

def init():
    Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
        init()