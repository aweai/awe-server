"""stats

Revision ID: 391a5784e4d0
Revises: d084fee4a187
Create Date: 2024-12-19 15:57:32.550562

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
import awe


# revision identifiers, used by Alembic.
revision: str = '391a5784e4d0'
down_revision: Union[str, None] = 'd084fee4a187'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('useragentstatsinvocationdailycounts',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('day', sa.Integer(), nullable=False),
    sa.Column('user_agent_id', sa.Integer(), nullable=False),
    sa.Column('tool', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('invocations', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_useragentstatsinvocationdailycounts_day'), 'useragentstatsinvocationdailycounts', ['day'], unique=False)
    op.create_index(op.f('ix_useragentstatsinvocationdailycounts_tool'), 'useragentstatsinvocationdailycounts', ['tool'], unique=False)
    op.create_index(op.f('ix_useragentstatsinvocationdailycounts_user_agent_id'), 'useragentstatsinvocationdailycounts', ['user_agent_id'], unique=False)
    op.create_table('useragentstatsinvocations',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_agent_id', sa.Integer(), nullable=False),
    sa.Column('tg_user_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('tool', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('created_at', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_useragentstatsinvocations_created_at'), 'useragentstatsinvocations', ['created_at'], unique=False)
    op.create_index(op.f('ix_useragentstatsinvocations_tg_user_id'), 'useragentstatsinvocations', ['tg_user_id'], unique=False)
    op.create_index(op.f('ix_useragentstatsinvocations_user_agent_id'), 'useragentstatsinvocations', ['user_agent_id'], unique=False)
    op.create_table('useragentstatstokentransferdailycounts',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('day', sa.Integer(), nullable=False),
    sa.Column('user_agent_id', sa.Integer(), nullable=False),
    sa.Column('transactions', sa.Integer(), nullable=False),
    sa.Column('amount', sa.Integer(), nullable=False),
    sa.Column('addresses', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_useragentstatstokentransferdailycounts_day'), 'useragentstatstokentransferdailycounts', ['day'], unique=False)
    op.create_index(op.f('ix_useragentstatstokentransferdailycounts_user_agent_id'), 'useragentstatstokentransferdailycounts', ['user_agent_id'], unique=False)
    op.create_table('useragentstatstokentransfers',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_agent_id', sa.Integer(), nullable=False),
    sa.Column('tg_user_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('to_address', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('transfer_amount', sa.BigInteger(), nullable=True),
    sa.Column('created_at', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('useragentstatsuserdailycounts',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('day', sa.Integer(), nullable=False),
    sa.Column('user_agent_id', sa.Integer(), nullable=False),
    sa.Column('users', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_useragentstatsuserdailycounts_day'), 'useragentstatsuserdailycounts', ['day'], unique=False)
    op.create_index(op.f('ix_useragentstatsuserdailycounts_user_agent_id'), 'useragentstatsuserdailycounts', ['user_agent_id'], unique=False)
    op.drop_column('useragent', 'total_invocations')
    op.add_column('useragentdata', sa.Column('total_invocations', sa.Integer(), nullable=False))
    op.add_column('useragentdata', sa.Column('total_users', sa.Integer(), nullable=False))
    op.add_column('useragentdata', sa.Column('awe_token_total_transactions', sa.Integer(), nullable=False))
    op.add_column('useragentdata', sa.Column('awe_token_total_addresses', sa.Integer(), nullable=False))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('useragentdata', 'awe_token_total_addresses')
    op.drop_column('useragentdata', 'awe_token_total_transactions')
    op.drop_column('useragentdata', 'total_users')
    op.drop_column('useragentdata', 'total_invocations')
    op.add_column('useragent', sa.Column('total_invocations', sa.INTEGER(), nullable=False))
    op.drop_index(op.f('ix_useragentstatsuserdailycounts_user_agent_id'), table_name='useragentstatsuserdailycounts')
    op.drop_index(op.f('ix_useragentstatsuserdailycounts_day'), table_name='useragentstatsuserdailycounts')
    op.drop_table('useragentstatsuserdailycounts')
    op.drop_table('useragentstatstokentransfers')
    op.drop_index(op.f('ix_useragentstatstokentransferdailycounts_user_agent_id'), table_name='useragentstatstokentransferdailycounts')
    op.drop_index(op.f('ix_useragentstatstokentransferdailycounts_day'), table_name='useragentstatstokentransferdailycounts')
    op.drop_table('useragentstatstokentransferdailycounts')
    op.drop_index(op.f('ix_useragentstatsinvocations_user_agent_id'), table_name='useragentstatsinvocations')
    op.drop_index(op.f('ix_useragentstatsinvocations_tg_user_id'), table_name='useragentstatsinvocations')
    op.drop_index(op.f('ix_useragentstatsinvocations_created_at'), table_name='useragentstatsinvocations')
    op.drop_table('useragentstatsinvocations')
    op.drop_index(op.f('ix_useragentstatsinvocationdailycounts_user_agent_id'), table_name='useragentstatsinvocationdailycounts')
    op.drop_index(op.f('ix_useragentstatsinvocationdailycounts_tool'), table_name='useragentstatsinvocationdailycounts')
    op.drop_index(op.f('ix_useragentstatsinvocationdailycounts_day'), table_name='useragentstatsinvocationdailycounts')
    op.drop_table('useragentstatsinvocationdailycounts')
    # ### end Alembic commands ###
