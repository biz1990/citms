from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, with_loader_criteria
from sqlalchemy import event, select, and_
from backend.src.core.config import settings

engine = create_async_engine(
    settings.SQLALCHEMY_DATABASE_URI,
    echo=True,
    future=True,
    pool_size=20,
    max_overflow=10,
)

@event.listens_for(AsyncSession, "do_orm_execute")
def _add_soft_delete_filter(execute_state):
    """Global soft delete filter for all SELECT queries."""
    if (
        execute_state.is_select
        and not execute_state.is_column_load
        and not execute_state.is_relationship_load
    ):
        execute_state.statement = execute_state.statement.options(
            with_loader_criteria(
                lambda cls: cls.deleted_at == None,
                include_subclasses=True
            )
        )

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

class Base(DeclarativeBase):
    pass

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
