"""document pipeline schema

Revision ID: 0fc306283a7e
Revises: 81ba5eebd41d
Create Date: 2026-07-29 07:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import app.db.models


# revision identifiers, used by Alembic.
revision: str = '0fc306283a7e'
down_revision: Union[str, Sequence[str], None] = '81ba5eebd41d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('policy',
    sa.Column('id', app.db.models.GUID(), nullable=False),
    sa.Column('product_id', app.db.models.GUID(), nullable=False),
    sa.Column('name', sa.String(length=160), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['product_id'], ['product.id'], ),
    sa.PrimaryKeyConstraint('id')
    )

    # policy_version: product_id -> policy_id (direct, non-additive - see
    # models.py docstring; no production data exists yet so this is safe).
    with op.batch_alter_table('policy_version', schema=None) as batch_op:
        batch_op.add_column(sa.Column('policy_id', app.db.models.GUID(), nullable=True))
        batch_op.add_column(sa.Column('effective_date', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('created_at', sa.DateTime(), nullable=True))
    op.execute("DELETE FROM policy_version")  # no rows can have a valid policy_id yet
    with op.batch_alter_table('policy_version', schema=None) as batch_op:
        batch_op.alter_column('policy_id', nullable=False)
        batch_op.alter_column('created_at', nullable=False, server_default=sa.func.now())
        batch_op.create_foreign_key('fk_policy_version_policy', 'policy', ['policy_id'], ['id'])
        batch_op.drop_constraint('fk_policy_version_product_id', type_='foreignkey') if False else None
        batch_op.drop_column('product_id')

    op.create_table('document',
    sa.Column('id', app.db.models.GUID(), nullable=False),
    sa.Column('policy_version_id', app.db.models.GUID(), nullable=False),
    sa.Column('doc_type', sa.String(length=30), nullable=False),
    sa.Column('storage_key', sa.String(length=500), nullable=False),
    sa.Column('sha256_hash', sa.String(length=64), nullable=False),
    sa.Column('etag', sa.String(length=200), nullable=True),
    sa.Column('last_modified', sa.String(length=80), nullable=True),
    sa.Column('page_count', sa.Integer(), nullable=True),
    sa.Column('source_url', sa.String(length=1000), nullable=False),
    sa.Column('downloaded_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['policy_version_id'], ['policy_version.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('storage_key')
    )
    op.create_index(op.f('ix_document_sha256_hash'), 'document', ['sha256_hash'], unique=False)

    op.create_table('section',
    sa.Column('id', app.db.models.GUID(), nullable=False),
    sa.Column('policy_version_id', app.db.models.GUID(), nullable=False),
    sa.Column('document_id', app.db.models.GUID(), nullable=False),
    sa.Column('heading', sa.String(length=300), nullable=True),
    sa.Column('page_start', sa.Integer(), nullable=False),
    sa.Column('page_end', sa.Integer(), nullable=False),
    sa.Column('paragraph_ref', sa.String(length=40), nullable=True),
    sa.ForeignKeyConstraint(['document_id'], ['document.id'], ),
    sa.ForeignKeyConstraint(['policy_version_id'], ['policy_version.id'], ),
    sa.PrimaryKeyConstraint('id')
    )

    op.create_table('benefit',
    sa.Column('id', app.db.models.GUID(), nullable=False),
    sa.Column('section_id', app.db.models.GUID(), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('monetary_limit', sa.Numeric(precision=12, scale=2), nullable=True),
    sa.Column('percentage_limit', sa.Numeric(precision=5, scale=2), nullable=True),
    sa.Column('is_automatic', sa.Boolean(), nullable=False),
    sa.Column('page', sa.Integer(), nullable=False),
    sa.Column('paragraph_ref', sa.String(length=40), nullable=False),
    sa.Column('confidence', sa.Float(), nullable=False),
    sa.ForeignKeyConstraint(['section_id'], ['section.id'], ),
    sa.PrimaryKeyConstraint('id')
    )

    op.create_table('policy_limit',
    sa.Column('id', app.db.models.GUID(), nullable=False),
    sa.Column('section_id', app.db.models.GUID(), nullable=False),
    sa.Column('limit_type', sa.String(length=60), nullable=False),
    sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('currency', sa.String(length=3), nullable=False),
    sa.Column('page', sa.Integer(), nullable=False),
    sa.Column('paragraph_ref', sa.String(length=40), nullable=False),
    sa.Column('confidence', sa.Float(), nullable=False),
    sa.ForeignKeyConstraint(['section_id'], ['section.id'], ),
    sa.PrimaryKeyConstraint('id')
    )

    op.create_table('exclusion',
    sa.Column('id', app.db.models.GUID(), nullable=False),
    sa.Column('section_id', app.db.models.GUID(), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('page', sa.Integer(), nullable=False),
    sa.Column('paragraph_ref', sa.String(length=40), nullable=False),
    sa.Column('confidence', sa.Float(), nullable=False),
    sa.ForeignKeyConstraint(['section_id'], ['section.id'], ),
    sa.PrimaryKeyConstraint('id')
    )

    op.create_table('definition',
    sa.Column('id', app.db.models.GUID(), nullable=False),
    sa.Column('section_id', app.db.models.GUID(), nullable=False),
    sa.Column('term', sa.String(length=200), nullable=False),
    sa.Column('definition_text', sa.Text(), nullable=False),
    sa.Column('page', sa.Integer(), nullable=False),
    sa.Column('paragraph_ref', sa.String(length=40), nullable=False),
    sa.ForeignKeyConstraint(['section_id'], ['section.id'], ),
    sa.PrimaryKeyConstraint('id')
    )

    op.create_table('waiting_period',
    sa.Column('id', app.db.models.GUID(), nullable=False),
    sa.Column('section_id', app.db.models.GUID(), nullable=False),
    sa.Column('applies_to', sa.String(length=200), nullable=False),
    sa.Column('days', sa.Integer(), nullable=False),
    sa.Column('page', sa.Integer(), nullable=False),
    sa.Column('paragraph_ref', sa.String(length=40), nullable=False),
    sa.Column('confidence', sa.Float(), nullable=False),
    sa.ForeignKeyConstraint(['section_id'], ['section.id'], ),
    sa.PrimaryKeyConstraint('id')
    )

    op.create_table('optional_benefit',
    sa.Column('id', app.db.models.GUID(), nullable=False),
    sa.Column('section_id', app.db.models.GUID(), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('additional_premium', sa.Numeric(precision=12, scale=2), nullable=True),
    sa.Column('page', sa.Integer(), nullable=False),
    sa.Column('paragraph_ref', sa.String(length=40), nullable=False),
    sa.ForeignKeyConstraint(['section_id'], ['section.id'], ),
    sa.PrimaryKeyConstraint('id')
    )

    # eligibility_rule.document_id / graded_fact.document_id: add real FK
    # constraints now that document.id exists (columns were already
    # unconstrained nullable UUIDs from the first migration).
    with op.batch_alter_table('eligibility_rule', schema=None) as batch_op:
        batch_op.create_foreign_key('fk_eligibility_rule_document', 'document', ['document_id'], ['id'])

    with op.batch_alter_table('graded_fact', schema=None) as batch_op:
        batch_op.create_foreign_key('fk_graded_fact_document', 'document', ['document_id'], ['id'])


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('graded_fact', schema=None) as batch_op:
        batch_op.drop_constraint('fk_graded_fact_document', type_='foreignkey')

    with op.batch_alter_table('eligibility_rule', schema=None) as batch_op:
        batch_op.drop_constraint('fk_eligibility_rule_document', type_='foreignkey')

    op.drop_table('optional_benefit')
    op.drop_table('waiting_period')
    op.drop_table('definition')
    op.drop_table('exclusion')
    op.drop_table('policy_limit')
    op.drop_table('benefit')
    op.drop_table('section')
    op.drop_index(op.f('ix_document_sha256_hash'), table_name='document')
    op.drop_table('document')

    # policy_version: restore product_id (empty on restore - acceptable,
    # there's no live data at risk in this environment).
    with op.batch_alter_table('policy_version', schema=None) as batch_op:
        batch_op.add_column(sa.Column('product_id', app.db.models.GUID(), nullable=True))
        batch_op.drop_constraint('fk_policy_version_policy', type_='foreignkey')
        batch_op.drop_column('created_at')
        batch_op.drop_column('effective_date')
        batch_op.drop_column('policy_id')

    op.drop_table('policy')
