"""rename and refactor singlepoint

Revision ID: 160352419195
Revises: 88e6b7d536d0
Create Date: 2021-11-12 13:43:15.488344

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "160352419195"
down_revision = "88e6b7d536d0"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###

    driver_enum = postgresql.ENUM("energy", "gradient", "hessian", "properties", name="driverenum", create_type=False)

    ########################################
    # Create singlepoint_specification table
    op.create_table(
        "singlepoint_specification",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("program", sa.String(length=100), nullable=False),
        sa.Column("driver", driver_enum, nullable=False),
        sa.Column("method", sa.String(length=100), nullable=False),
        sa.Column("basis", sa.String(length=100), nullable=False),
        sa.Column("keywords_id", sa.Integer(), nullable=False),
        sa.Column("protocols", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint("basis = LOWER(basis)", name="ck_singlepoint_specification_basis_lower"),
        sa.CheckConstraint("method = LOWER(method)", name="ck_singlepoint_specification_method_lower"),
        sa.CheckConstraint("program = LOWER(program)", name="ck_singlepoint_specification_program_lower"),
        sa.ForeignKeyConstraint(
            ["keywords_id"],
            ["keywords.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "program", "driver", "method", "basis", "keywords_id", "protocols", name="ux_singlepoint_specification_keys"
        ),
    )
    op.create_index("ix_singlepoint_specification_program", "singlepoint_specification", ["program"], unique=False)
    op.create_index("ix_singlepoint_specification_driver", "singlepoint_specification", ["driver"], unique=False)
    op.create_index("ix_singlepoint_specification_method", "singlepoint_specification", ["method"], unique=False)
    op.create_index("ix_singlepoint_specification_basis", "singlepoint_specification", ["basis"], unique=False)
    op.create_index(
        "ix_singlepoint_specification_keywords_id", "singlepoint_specification", ["keywords_id"], unique=False
    )
    op.create_index("ix_singlepoint_specification_protocols", "singlepoint_specification", ["protocols"], unique=False)

    ########################################
    # Add columns to the specification table, and rename some columns
    op.add_column("result", sa.Column("specification_id", sa.Integer(), nullable=True))  # Temporarily nullable
    op.create_index("ix_singlepoint_record_specification_id", "result", ["specification_id"], unique=False)
    op.create_foreign_key(
        "singlepoint_record_specification_id_fkey", "result", "singlepoint_specification", ["specification_id"], ["id"]
    )

    # op.drop_constraint("result_molecule_fkey", "result", type_="foreignkey")
    op.alter_column("result", "molecule", new_column_name="molecule_id")
    op.alter_column(
        "result",
        "properties",
        existing_type=postgresql.JSON(astext_type=sa.Text()),
        type_=postgresql.JSONB(astext_type=sa.Text()),
        existing_nullable=True,
    )

    op.execute(
        sa.text("ALTER TABLE result RENAME CONSTRAINT result_molecule_fkey TO singlepoint_record_molecule_id_fkey")
    )

    ########################################
    # Now for the data migration
    # Adding the empty keyword surrogate
    op.execute(
        sa.text(
            """INSERT INTO keywords (hash_index, values, lowercase, exact_floats, comments)
               VALUES ('bf21a9e8fbc5a3846fb05b4fa0859e0917b2202f',
                   '{}'::json,
                   true,
                   false,
                   'Empty keywords - use program defaults'
                   )
               ON CONFLICT DO NOTHING;"""
        )
    )

    res = op.get_bind().execute(
        sa.text("SELECT id FROM keywords WHERE hash_index = 'bf21a9e8fbc5a3846fb05b4fa0859e0917b2202f'")
    )
    empty_kw = res.scalar()

    ########################################
    # Update protocols to remove defaults and null
    # Column is not nullable, but sometimes stores json null
    op.execute(
        sa.text(
            r"""
               UPDATE base_record
               SET protocols = '{}'::jsonb
               WHERE protocols = 'null'::jsonb
               """
        )
    )

    # Remove default wavefunction
    op.execute(
        sa.text(
            r"""
               UPDATE base_record
               SET protocols = (protocols - 'wavefunction')
               WHERE record_type = 'singlepoint'
               AND protocols @> '{"wavefunction": "none"}'::jsonb;
               """
        )
    )

    # Remove default stdout
    op.execute(
        sa.text(
            r"""
               UPDATE base_record
               SET protocols = (protocols - 'stdout')
               WHERE record_type = 'singlepoint'
               AND protocols @> '{"stdout": true}'::jsonb;
               """
        )
    )

    # Remove default error correction protocol
    op.execute(
        sa.text(
            r"""
               UPDATE base_record
               SET protocols = (protocols #- '{error_correction,default_policy}')
               WHERE record_type = 'singlepoint'
               AND protocols @> '{"error_correction": {"default_policy": true}}'::jsonb
               """
        )
    )

    op.execute(
        sa.text(
            r"""
               UPDATE base_record
               SET protocols = (protocols #- '{error_correction,policies}')
               WHERE record_type = 'singlepoint'
               AND protocols->'error_correction'->'policies' = 'null'::jsonb
               OR protocols->'error_correction'->'policies' = '{}'::jsonb;
               """
        )
    )

    op.execute(
        sa.text(
            r"""
               UPDATE base_record
               SET protocols = (protocols - 'error_correction')
               WHERE record_type = 'singlepoint'
               AND protocols->'error_correction' = '{}'::jsonb;
               """
        )
    )

    ########################################
    # Populate the singlepoint_specification table
    # Coalesce null basis set, keywords, protocols into something not null
    op.execute(
        sa.text(
            f"""
               INSERT INTO singlepoint_specification (program, driver, method, basis, keywords_id, protocols)
               SELECT DISTINCT r.program,
                               r.driver::driverenum,
                               r.method,
                               COALESCE(r.basis, ''),
                               COALESCE(r.keywords, {empty_kw}),
                               COALESCE(br.protocols, '{{}}'::jsonb)
               FROM result r INNER JOIN base_record br on r.id = br.id;
               """
        )
    )

    op.execute(
        sa.text(
            f"""
              UPDATE result AS r
              SET specification_id = ss.id
              FROM singlepoint_specification AS ss, base_record as br
              WHERE r.id = br.id
              AND ss.program = r.program
              AND ss.driver = r.driver::driverenum
              AND ss.method = r.method
              AND ss.basis = COALESCE(r.basis, '')
              AND ss.keywords_id = COALESCE(r.keywords, {empty_kw})
              AND ss.protocols = COALESCE(br.protocols, '{{}}'::jsonb);
            """
        )
    )

    ##############################################
    # Add & populate foreign keys on wavefunction store
    op.add_column("wavefunction_store", sa.Column("record_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "wavefunction_store_record_id_fkey", "wavefunction_store", "result", ["record_id"], ["id"], ondelete="CASCADE"
    )
    op.create_unique_constraint("ux_wavefunction_store_record_id", "wavefunction_store", ["record_id"])

    op.execute(
        sa.text(
            f"""
              UPDATE wavefunction_store SET record_id = result.id
              FROM result
              WHERE result.wavefunction_data_id = wavefunction_store.id
            """
        )
    )

    # Populate some columns of wavefunction based on the "wavefunction" dictionary column of result
    op.execute(
        sa.text(
            f"""
              UPDATE wavefunction_store SET
              orbitals_a = result.wavefunction->'return_map'->'orbitals_a',
              orbitals_b = result.wavefunction->'return_map'->'orbitals_b',
              density_a = result.wavefunction->'return_map'->'density_a',
              density_b = result.wavefunction->'return_map'->'density_b',
              fock_a = result.wavefunction->'return_map'->'fock_a',
              fock_b = result.wavefunction->'return_map'->'fock_b',
              eigenvalues_a = result.wavefunction->'return_map'->'eigenvalues_a',
              eigenvalues_b = result.wavefunction->'return_map'->'eigenvalues_b',
              occupations_a = result.wavefunction->'return_map'->'occupations_a',
              occupations_b = result.wavefunction->'return_map'->'occupations_b'
              FROM result
              WHERE result.wavefunction_data_id = wavefunction_store.id
            """
        )
    )

    ########################################
    # rename some indices and constraints
    op.drop_index("ix_results_molecule", table_name="result")
    op.create_index("ix_singlepoint_record_molecule_id", "result", ["molecule_id"], unique=False)

    op.execute(sa.text("ALTER TABLE result RENAME CONSTRAINT result_id_fkey TO singlepoint_record_id_fkey"))

    # Now drop the unused columns/constraints/indices
    op.drop_constraint("result_wavefunction_data_id_fkey", "result", type_="foreignkey")
    op.drop_constraint("uix_results_keys", "result", type_="unique")
    op.drop_constraint("result_keywords_fkey", "result", type_="foreignkey")
    op.drop_column("result", "program")
    op.drop_column("result", "driver")
    op.drop_column("result", "method")
    op.drop_column("result", "basis")
    op.drop_column("result", "keywords")
    op.drop_column("result", "wavefunction_data_id")
    op.drop_column("result", "wavefunction")

    # Now make stuff not nullable
    op.alter_column("result", "specification_id", nullable=False)
    op.alter_column("wavefunction_store", "record_id", nullable=False)

    # Now rename the table
    op.rename_table("result", "singlepoint_record")
    op.execute(sa.text("ALTER INDEX result_pkey RENAME TO singlepoint_record_pkey"))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    raise RuntimeError("Cannot downgrade")
