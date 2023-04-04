"""statements column

Revision ID: e8961e181613
Revises: bb8e2be0af5b
Create Date: 2023-04-04 07:45:17.077550

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'e8961e181613'
down_revision = 'bb8e2be0af5b'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('safety_data_sheets',
                  sa.Column('statements', sa.ARRAY(sa.String()),
                            server_default='{}', nullable=False))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('safety_data_sheets', 'statements')
    # ### end Alembic commands ###