"""rename user.email to user.username

Revision ID: 0002_user_username
Revises: 0001_initial_schema
Create Date: 2026-07-18

NOVO: parte da mudança de login de e-mail para usuário. Só é necessária para
quem já tinha um banco criado com a migration 0001 antiga. Bancos novos
(SQLite criado do zero por db.create_all()) já nascem com a coluna certa e
não precisam rodar isto.

Usamos batch_alter_table porque o SQLite não suporta ALTER COLUMN direto —
o Alembic recria a tabela por baixo dos panos nesse modo. Em PostgreSQL o
batch mode também funciona normalmente (vira um ALTER COLUMN de verdade).
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_user_username"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("user") as batch_op:
        batch_op.alter_column(
            "email",
            new_column_name="username",
            existing_type=sa.String(length=120),
            type_=sa.String(length=80),
        )


def downgrade():
    with op.batch_alter_table("user") as batch_op:
        batch_op.alter_column(
            "username",
            new_column_name="email",
            existing_type=sa.String(length=80),
            type_=sa.String(length=120),
        )
