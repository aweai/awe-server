"""tg user payment

Revision ID: 99ff8881ef99
Revises: 7e18b3dd118b
Create Date: 2024-12-25 11:44:45.526987

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
import awe


# revision identifiers, used by Alembic.
revision: str = '99ff8881ef99'
down_revision: Union[str, None] = '7e18b3dd118b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('tgphantomusednonce',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('nonce', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('created_at', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('nonce')
    )
    with op.batch_alter_table('tgbotuserwallet', schema=None) as batch_op:
        batch_op.add_column(sa.Column('session', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
        batch_op.alter_column('address',
               existing_type=sa.VARCHAR(255),
               nullable=True)

    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('tgbotuserwallet', schema=None) as batch_op:
        batch_op.alter_column('address',
               existing_type=sa.VARCHAR(255),
               nullable=False)
        batch_op.drop_column('session')

    op.drop_table('tgphantomusednonce')
    # ### end Alembic commands ###
