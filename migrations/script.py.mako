# -*- coding: utf-8 -*-
# type: ignore

"""Generic single-database configuration."""

from alembic import context

# revision identifiers, used by Alembic.
revision = context.get_head_revision()
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
