from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings

# The engine holds the connection pool to your Supabase PostgreSQL.
# echo=True prints every SQL query to your terminal — great for learning.
# When you deploy to production, set echo=False.
engine = create_async_engine(
    settings.database_url,
    echo=True,
    
)

# A "session" is one database conversation.
# expire_on_commit=False means your data objects stay usable after a commit.
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Every database model (table) inherits from this.
class Base(DeclarativeBase):
    pass

# This is a FastAPI "dependency".
# When an endpoint needs the database, FastAPI calls this function,
# gives the endpoint a session to use, then closes it when done.
async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()