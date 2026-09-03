import uvicorn

from atlas.api import create_app
from atlas.config import get_settings
from atlas.infrastructure.database import Database
from atlas.infrastructure.database.repositories import AtlasRepository
from atlas.infrastructure.storage import S3ObjectStorage

settings = get_settings()
database = Database(settings)
repository = AtlasRepository(database.sessions)
storage = S3ObjectStorage(settings)
app = create_app(
    repository=repository,
    settings=settings,
    database=database,
    storage=storage,
)


def run() -> None:
    uvicorn.run(app, host=settings.api_host, port=settings.api_port)


if __name__ == "__main__":
    run()
