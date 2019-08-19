"""Add collection tables (dataset, reaction_dataset)

Revision ID: 129ff3ce9247
Revises: e32b61e2516f
Create Date: 2019-08-19 16:35:19.100113

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '129ff3ce9247'
down_revision = 'e32b61e2516f'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('dataset',
    sa.Column('default_benchmark', sa.String(), nullable=True),
    sa.Column('default_keywords', sa.JSON(), nullable=True),
    sa.Column('default_driver', sa.String(), nullable=True),
    sa.Column('default_units', sa.String(), nullable=True),
    sa.Column('alias_keywords', sa.JSON(), nullable=True),
    sa.Column('default_program', sa.String(), nullable=True),
    sa.Column('contributed_values', sa.JSON(), nullable=True),
    sa.Column('provenance', sa.JSON(), nullable=True),
    sa.Column('history_keys', sa.ARRAY(sa.String(), as_tuple=True), nullable=True),
    sa.Column('history', sa.ARRAY(sa.String(), as_tuple=True), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['id'], ['collection.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('reaction_dataset',
    sa.Column('default_benchmark', sa.String(), nullable=True),
    sa.Column('default_keywords', sa.JSON(), nullable=True),
    sa.Column('default_driver', sa.String(), nullable=True),
    sa.Column('default_units', sa.String(), nullable=True),
    sa.Column('alias_keywords', sa.JSON(), nullable=True),
    sa.Column('default_program', sa.String(), nullable=True),
    sa.Column('contributed_values', sa.JSON(), nullable=True),
    sa.Column('provenance', sa.JSON(), nullable=True),
    sa.Column('history_keys', sa.ARRAY(sa.String(), as_tuple=True), nullable=True),
    sa.Column('history', sa.ARRAY(sa.String(), as_tuple=True), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('ds_type', sa.String(), nullable=True),
    sa.ForeignKeyConstraint(['id'], ['collection.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('dataset_records',
    sa.Column('dataset_id', sa.Integer(), nullable=False),
    sa.Column('molecule_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('comment', sa.String(), nullable=True),
    sa.Column('local_results', sa.JSON(), nullable=True),
    sa.ForeignKeyConstraint(['dataset_id'], ['dataset.id'], ondelete='cascade'),
    sa.ForeignKeyConstraint(['molecule_id'], ['molecule.id'], ondelete='cascade'),
    sa.PrimaryKeyConstraint('dataset_id', 'molecule_id')
    )
    op.create_table('reaction_dataset_records',
    sa.Column('reaction_dataset_id', sa.Integer(), nullable=False),
    sa.Column('attributes', sa.JSON(), nullable=True),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('reaction_results', sa.JSON(), nullable=True),
    sa.Column('stoichiometry', sa.JSON(), nullable=True),
    sa.Column('extras', sa.JSON(), nullable=True),
    sa.ForeignKeyConstraint(['reaction_dataset_id'], ['reaction_dataset.id'], ondelete='cascade'),
    sa.PrimaryKeyConstraint('reaction_dataset_id', 'name')
    )
    op.add_column('collection', sa.Column('collection_type', sa.String(), nullable=True))
    op.create_index('ix_collection_type', 'collection', ['collection_type'], unique=False)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index('ix_collection_type', table_name='collection')
    op.drop_column('collection', 'collection_type')
    op.drop_table('reaction_dataset_records')
    op.drop_table('dataset_records')
    op.drop_table('reaction_dataset')
    op.drop_table('dataset')
    # ### end Alembic commands ###
