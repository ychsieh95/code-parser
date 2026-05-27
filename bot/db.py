import aiosqlite
from pathlib import Path

DB_PATH = Path(__file__).parent / "config/channel_settings.db"


class Database:
    def __init__(self):
        self._db: aiosqlite.Connection | None = None
        self._cache: dict[int, set[str]] = {}

    async def connect(self) -> None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(DB_PATH)
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS channel_modes (
                channel_id INTEGER NOT NULL,
                mode       TEXT    NOT NULL,
                PRIMARY KEY (channel_id, mode)
            )
        """)
        await self._db.commit()
        self._cache = await self._load_all()

    async def close(self) -> None:
        if self._db:
            await self._db.close()

    async def _load_all(self) -> dict[int, set[str]]:
        async with self._db.execute("SELECT channel_id, mode FROM channel_modes") as cursor:
            rows = await cursor.fetchall()
        result: dict[int, set[str]] = {}
        for channel_id, mode in rows:
            result.setdefault(channel_id, set()).add(mode)
        return result

    def get_modes(self, channel_id: int) -> set[str]:
        """Synchronous cache read — safe for use in on_message hot path."""
        return self._cache.get(channel_id, set())

    async def get_all_modes(self) -> dict[int, set[str]]:
        return dict(self._cache)

    async def enable_mode(self, channel_id: int, mode: str) -> bool:
        """Returns True if the mode was newly enabled."""
        cursor = await self._db.execute(
            "INSERT OR IGNORE INTO channel_modes (channel_id, mode) VALUES (?, ?)",
            (channel_id, mode),
        )
        await self._db.commit()
        if cursor.rowcount > 0:
            self._cache.setdefault(channel_id, set()).add(mode)
            return True
        return False

    async def disable_mode(self, channel_id: int, mode: str) -> bool:
        """Returns True if the mode was actually disabled."""
        cursor = await self._db.execute(
            "DELETE FROM channel_modes WHERE channel_id = ? AND mode = ?",
            (channel_id, mode),
        )
        await self._db.commit()
        if cursor.rowcount > 0:
            self._cache.get(channel_id, set()).discard(mode)
            return True
        return False
