import sys
import os
from pathlib import Path
import pytest
import pytest_asyncio

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

os.environ["TESTING"] = "1"

from backend.app.db.database import engine, Base, AsyncSessionLocal
from backend.app.db.seed import seed_initial_data

@pytest_asyncio.fixture(scope="session", autouse=True)
async def init_test_db():
    """Create all tables and seed data for the test session."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with AsyncSessionLocal() as session:
        await seed_initial_data(session)
    
    yield
