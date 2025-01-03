"""collect user staking

Revision ID: 35e3083dbc4a
Revises: 53527661156b
Create Date: 2025-01-02 20:25:15.160674

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
import awe


# revision identifiers, used by Alembic.
revision: str = '35e3083dbc4a'
down_revision: Union[str, None] = '53527661156b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('userstaking', schema=None) as batch_op:
        batch_op.add_column(sa.Column('tx_hash', sqlmodel.sql.sqltypes.AutoString(), nullable=False))

    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('userstaking', schema=None) as batch_op:
        batch_op.drop_column('tx_hash')

    # ### end Alembic commands ###