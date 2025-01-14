"""agent score

Revision ID: 7c2599651a42
Revises: aed2c1074de6
Create Date: 2025-01-14 00:37:29.319251

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
import awe


# revision identifiers, used by Alembic.
revision: str = '7c2599651a42'
down_revision: Union[str, None] = 'aed2c1074de6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('useragent', schema=None) as batch_op:
        batch_op.add_column(sa.Column('score', sa.Integer(), nullable=False, server_default='0'))

    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('useragent', schema=None) as batch_op:
        batch_op.drop_column('score')

    # ### end Alembic commands ###
