# -*- coding: utf-8 -*-
"""Revision ID: 0002_create_transfers_idempotency
Revises: 0001
Create Date: 2026-10-26 12:50:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0002_create_transfers_idempotency'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'transfers',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('from_account_id', sa.String(), nullable=False),
        sa.Column('to_account_id', sa.String(), nullable=False),
        sa.Column('amount_piastres', sa.Integer(), nullable=False),
        sa.Column('memo', sa.String(length=140), nullable=True),
        sa.Column('status', sa.String(), nullable=False),
        sa.CheckConstraint('amount_piastres > 0', name='ck_transfers_amount_positive'),
        sa.ForeignKeyConstraint(['from_account_id'], ['accounts.id'], ),
        sa.ForeignKeyConstraint(['to_account_id'], ['accounts.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table(
        'idempotency_records',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('customer_id', sa.String(), nullable=False),
        sa.Column('key', sa.String(), nullable=False),
        sa.Column('request_hash', sa.String(), nullable=False),
        sa.Column('status_code', sa.Integer(), nullable=False),
        sa.Column('response_body', sa.String(), nullable=False),
        sa.Column('transfer_id', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('customer_id', 'key', name='uq_idempotency_customer_key')
    )


def downgrade() -> None:
    op.drop_table('idempotency_records')
    op.drop_table('transfers')
