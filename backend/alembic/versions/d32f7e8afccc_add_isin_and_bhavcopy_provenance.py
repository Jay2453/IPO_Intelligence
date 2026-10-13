"""add_isin_and_bhavcopy_provenance

Revision ID: d32f7e8afccc
Revises: 104755505a20
Create Date: 2026-10-11 18:31:35.599236

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd32f7e8afccc'
down_revision: Union[str, None] = '104755505a20'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('ipos', schema=None) as batch_op:
        batch_op.add_column(sa.Column('isin', sa.String(length=12), nullable=True))
        batch_op.add_column(sa.Column('bse_scrip_code', sa.String(length=20), nullable=True))
        batch_op.create_index(batch_op.f('ix_ipos_isin'), ['isin'], unique=False)
        batch_op.create_index(batch_op.f('ix_ipos_bse_scrip_code'), ['bse_scrip_code'], unique=False)

    with op.batch_alter_table('market_observations', schema=None) as batch_op:
        batch_op.add_column(sa.Column('exchange', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('source_url', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('source_file_hash', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('raw_data_provenance', sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('market_observations', schema=None) as batch_op:
        batch_op.drop_column('raw_data_provenance')
        batch_op.drop_column('source_file_hash')
        batch_op.drop_column('source_url')
        batch_op.drop_column('exchange')

    with op.batch_alter_table('ipos', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_ipos_bse_scrip_code'))
        batch_op.drop_index(batch_op.f('ix_ipos_isin'))
        batch_op.drop_column('bse_scrip_code')
        batch_op.drop_column('isin')
