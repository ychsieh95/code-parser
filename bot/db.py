import aiosqlite
from bot.constants import READ_ACTION_NONE
from pathlib import Path

DB_PATH = Path(__file__).parent / "config/channel_settings.db"


class Database:
    def __init__(self):
        self._db: aiosqlite.Connection | None = None
        self._cache: dict[int, set[str]] = {}
        self._deletion_cache: dict[int, bool] = {}
        self._read_action_cache: dict[int, str] = {}

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
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS channel_message_deletion (
                channel_id INTEGER NOT NULL PRIMARY KEY,
                enabled    INTEGER NOT NULL
            )
        """)
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS channel_read_action (
                channel_id INTEGER NOT NULL PRIMARY KEY,
                mode       TEXT    NOT NULL
            )
        """)
        await self._db.commit()
        self._cache             = await self._load_all()
        self._deletion_cache    = await self._load_deletion_settings()
        self._read_action_cache = await self._load_read_action_settings()

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

    async def _load_deletion_settings(self) -> dict[int, bool]:
        async with self._db.execute("SELECT channel_id, enabled FROM channel_message_deletion") as cursor:
            rows = await cursor.fetchall()
        return {channel_id: bool(enabled) for channel_id, enabled in rows}

    async def _load_read_action_settings(self) -> dict[int, str]:
        async with self._db.execute("SELECT channel_id, mode FROM channel_read_action") as cursor:
            rows = await cursor.fetchall()
        return {channel_id: mode for channel_id, mode in rows}

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

    def message_deletion_enabled(self, channel_id: int) -> bool:
        """Synchronous cache read — safe for use in on_message hot path. Defaults to enabled."""
        return self._deletion_cache.get(channel_id, True)

    async def set_message_deletion(self, channel_id: int, enabled: bool) -> bool:
        """Returns True if the setting was actually changed."""
        if self._deletion_cache.get(channel_id, True) == enabled:
            return False
        await self._db.execute(
            """
            INSERT INTO channel_message_deletion (channel_id, enabled) VALUES (?, ?)
            ON CONFLICT(channel_id) DO UPDATE SET enabled = excluded.enabled
            """,
            (channel_id, int(enabled)),
        )
        await self._db.commit()
        self._deletion_cache[channel_id] = enabled
        return True

    def read_action(self, channel_id: int) -> str:
        """Synchronous cache read — safe for use in on_message hot path. Defaults to 'none'."""
        return self._read_action_cache.get(channel_id, READ_ACTION_NONE)

    async def set_read_action(self, channel_id: int, mode: str) -> bool:
        """Returns True if the setting was actually changed."""
        if self._read_action_cache.get(channel_id, READ_ACTION_NONE) == mode:
            return False
        await self._db.execute(
            """
            INSERT INTO channel_read_action (channel_id, mode) VALUES (?, ?)
            ON CONFLICT(channel_id) DO UPDATE SET mode = excluded.mode
            """,
            (channel_id, mode),
        )
        await self._db.commit()
        self._read_action_cache[channel_id] = mode
        return True

    async def disable_mode(self, channel_id: int, mode: str) -> bool:
        """Returns True if the mode was actually disabled."""
        cursor = await self._db.execute(
            "DELETE FROM channel_modes WHERE channel_id = ? AND mode = ?",
            (channel_id, mode),
        )
        await self._db.commit()
        if cursor.rowcount > 0:
            modes = self._cache.get(channel_id, set())
            modes.discard(mode)
            if not modes:
                self._cache.pop(channel_id, None)
            return True
        return False
