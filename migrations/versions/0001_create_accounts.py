# -*- coding: utf-8 -*-
"""Revision ID: 0001_create_accounts
Revises: 
Create Date: 2026-10-26 12:40:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'accounts',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('customer_id', sa.String(), nullable=False),
        sa.Column('balance_piastres', sa.Integer(), nullable=False),
        sa.CheckConstraint('balance_piastres >= 0', name='ck_accounts_balance_non_negative'),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('accounts')
