"""Add editor-owned resort planning fields, separate from supplier content."""
from alembic import op
import sqlalchemy as sa

revision = 'c5a20261003'
down_revision = '8865344861fc'
branch_labels = None
depends_on = None


def upgrade():
    for name, length in [('planning_tags', 250), ('planning_source', 1000), ('planning_reviewed', 10),
                         ('unavailable_from', 10), ('unavailable_to', 10)]:
        op.add_column('resort', sa.Column(name, sa.String(length), nullable=False, server_default=''))
    for name in ('consideration', 'advisor_notes'):
        op.add_column('resort', sa.Column(name, sa.Text(), nullable=False, server_default=''))


def downgrade():
    with op.batch_alter_table('resort') as batch:
        for name in ('planning_tags', 'planning_source', 'planning_reviewed', 'consideration',
                     'advisor_notes', 'unavailable_from', 'unavailable_to'):
            batch.drop_column(name)
