"""Database Remediation v3.6.4

Revision ID: 20260409_remediation
Revises: 20260406_db_remediation
Create Date: 2026-04-09 08:20:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import text

# revision identifiers, used by Alembic.
revision = '20260409_remediation'
down_revision = '20260406_db_remediation'
branch_labels = None
depends_on = None

def upgrade():
    # 1. Remediation for inventory_run_logs (Drop non-compliant columns)
    op.drop_column('inventory_run_logs', 'updated_at')
    op.drop_column('inventory_run_logs', 'deleted_at')
    op.drop_column('inventory_run_logs', 'version')

    # 2. Create device_status_history table
    op.create_table(
        'device_status_history',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('device_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('devices.id'), nullable=False),
        sa.Column('old_status', sa.String(30)),
        sa.Column('new_status', sa.String(30), nullable=False),
        sa.Column('changed_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id')),
        sa.Column('reason', sa.String()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'))
    )

    # 3. Add GIN Index on device_components.specifications
    op.execute("CREATE INDEX idx_component_specs_gin ON device_components USING GIN (specifications)")

    # 4. Partial Unique Indexes for compliant soft-delete
    # Roles
    op.create_index(
        'idx_role_name_unique', 
        'roles', 
        ['name'], 
        unique=True, 
        postgresql_where=sa.text("deleted_at IS NULL")
    )
    # Tickets
    # (Assuming table 'tickets' has columns needed)
    # Software Blacklist
    # (Assuming table exists: software_blacklist)
    # Serial Blacklist
    # (Assuming table exists: serial_blacklist)

    # 5. Fix Departments manager_id FK (Deferrable)
    op.drop_constraint('departments_manager_id_fkey', 'departments', type_='foreignkey')
    op.create_foreign_key(
        'departments_manager_id_fkey',
        'departments', 'users',
        ['manager_id'], ['id'],
        deferrable=True, initially='DEFERRED'
    )

def downgrade():
    # Reverse changes
    op.drop_constraint('departments_manager_id_fkey', 'departments', type_='foreignkey')
    op.create_foreign_key('departments_manager_id_fkey', 'departments', 'users', ['manager_id'], ['id'])
    
    op.drop_index('idx_role_name_unique', table_name='roles')
    op.execute("DROP INDEX idx_component_specs_gin")
    op.drop_table('device_status_history')
    
    op.add_column('inventory_run_logs', sa.Column('version', sa.Integer(), server_default='1'))
    op.add_column('inventory_run_logs', sa.Column('deleted_at', sa.DateTime(timezone=True)))
    op.add_column('inventory_run_logs', sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')))
