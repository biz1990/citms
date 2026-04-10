import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
from backend.src.infrastructure.database import Base
# Import all models to register them with metadata
from backend.src.contexts.auth.models import User, Role, Permission, RolePermission, UserRole, Department, AuditLog
from backend.src.contexts.asset.models import Location, Device, DeviceComponent, DeviceConnection
from backend.src.contexts.inventory.models import SoftwareCatalog, SoftwareInstallation, InventoryRunLog
from backend.src.contexts.itsm.models import Ticket, TicketComment, MaintenanceLog, SystemHoliday
from backend.src.contexts.license.models import SoftwareLicense, SerialBlacklist, SoftwareBlacklist
from backend.src.contexts.procurement.models import Vendor, Contract, PurchaseOrder, PurchaseItem
from backend.src.contexts.workflow.models import WorkflowRequest, DeviceAssignment, ApprovalHistory
from backend.src.contexts.notification.models import Notification, NotificationPreference
from backend.src.infrastructure.settings_repository import SystemSetting

target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


from backend.src.core.config import settings

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = settings.DATABASE_URL
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "pyformat"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    from sqlalchemy.ext.asyncio import create_async_engine
    connectable = create_async_engine(
        settings.DATABASE_URL,
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
