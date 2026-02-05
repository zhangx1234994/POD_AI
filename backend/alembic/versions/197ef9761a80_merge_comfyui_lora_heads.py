"""merge comfyui lora heads

Revision ID: 197ef9761a80
Revises: f310ca291324, 20260204_add_comfyui_lora_base_models
Create Date: 2026-02-05 01:40:34.534504

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '197ef9761a80'
down_revision: Union[str, Sequence[str], None] = ('f310ca291324', '20260204_add_comfyui_lora_base_models')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
