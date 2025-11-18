from __future__ import annotations

import json
import os
import secrets
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Sequence

import aiosqlite


@dataclass(slots=True)
class OrderRecord:
    order_id: int
    user_id: int
    username: Optional[str]
    source: str
    state: str
    start_token: Optional[str]
    geo: Optional[str]
    method_user_text: Optional[str]
    tests_count: Optional[int]
    withdraw_required: Optional[bool]
    custom_test_required: Optional[bool]
    custom_test_text: Optional[str]
    kyc_required: Optional[bool]
    comments: Optional[str]
    site_url: Optional[str]
    login: Optional[str]
    password_enc: Optional[str]
    payout_surcharge: Optional[int]
    price_eur: Optional[int]
    status: str
    payment_network: Optional[str]
    payment_wallet: Optional[str]
    payment_txid: Optional[str]
    payment_proof_file_id: Optional[str]
    admin_notes: Optional[str]
    payload_hash: Optional[str]
    tg_user_id: Optional[int]
    email: Optional[str]
    created_at: str
    updated_at: str


@dataclass(slots=True)
class OrderCreate:
    source: str
    state: str
    start_token: str
    user_id: int
    username: Optional[str]
    geo: Optional[str]
    method_user_text: Optional[str]
    tests_count: Optional[int]
    withdraw_required: Optional[bool]
    custom_test_required: Optional[bool]
    custom_test_text: Optional[str]
    kyc_required: Optional[bool]
    comments: Optional[str]
    site_url: Optional[str]
    login: Optional[str]
    password_enc: Optional[str]
    payout_surcharge: Optional[int]
    price_eur: Optional[int]
    status: str
    payment_network: Optional[str]
    payment_wallet: Optional[str]
    payload_hash: Optional[str]
    tg_user_id: Optional[int]
    email: Optional[str]


@dataclass(slots=True)
class UserSettings:
    user_id: int
    language: str


class OrdersRepository:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        directory = os.path.dirname(os.path.abspath(db_path))
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)

    async def init(self) -> None:
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS orders (
                    order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    username TEXT,
                    source TEXT NOT NULL,
                    state TEXT NOT NULL,
                    start_token TEXT,
                    geo TEXT,
                    method_user_text TEXT,
                    tests_count INTEGER,
                    withdraw_required INTEGER,
                    custom_test_required INTEGER,
                    custom_test_text TEXT,
                    kyc_required INTEGER,
                    comments TEXT,
                    site_url TEXT,
                    login TEXT,
                    password_enc TEXT,
                    payout_surcharge INTEGER,
                    price_eur INTEGER,
                    status TEXT NOT NULL,
                    payment_network TEXT,
                    payment_wallet TEXT,
                    payment_txid TEXT,
                    payment_proof_file_id TEXT,
                    admin_notes TEXT,
                    payload_hash TEXT,
                    tg_user_id INTEGER,
                    email TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS user_settings (
                    user_id INTEGER PRIMARY KEY,
                    language TEXT NOT NULL
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS payload_cache (
                    token TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            await db.execute("CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_payload_cache_created_at ON payload_cache(created_at)")
            await self._ensure_columns(db)
            await db.commit()

    async def _ensure_columns(self, db: aiosqlite.Connection) -> None:
        cursor = await db.execute("PRAGMA table_info(orders)")
        columns = {row[1] for row in await cursor.fetchall()}
        alter_statements = []
        if "payout_surcharge" not in columns:
            alter_statements.append("ALTER TABLE orders ADD COLUMN payout_surcharge INTEGER DEFAULT 0")
        if "payload_hash" not in columns:
            alter_statements.append("ALTER TABLE orders ADD COLUMN payload_hash TEXT")
        if "state" not in columns:
            alter_statements.append("ALTER TABLE orders ADD COLUMN state TEXT DEFAULT 'draft'")
        if "start_token" not in columns:
            alter_statements.append("ALTER TABLE orders ADD COLUMN start_token TEXT")
        if "tg_user_id" not in columns:
            alter_statements.append("ALTER TABLE orders ADD COLUMN tg_user_id INTEGER")
        if "email" not in columns:
            alter_statements.append("ALTER TABLE orders ADD COLUMN email TEXT")
        for statement in alter_statements:
            await db.execute(statement)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_orders_state ON orders(state)")
        await db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_orders_start_token ON orders(start_token)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_orders_email ON orders(email)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_orders_tg_user ON orders(tg_user_id)")

    def generate_start_token(self) -> str:
        return secrets.token_urlsafe(8)

    async def create_order(self, payload: OrderCreate) -> int:
        now = datetime.utcnow().isoformat(timespec="seconds")
        fields: Dict[str, Any] = asdict(payload)
        if payload.withdraw_required is not None:
            fields["withdraw_required"] = int(payload.withdraw_required)
        if payload.custom_test_required is not None:
            fields["custom_test_required"] = int(payload.custom_test_required)
        if payload.kyc_required is not None:
            fields["kyc_required"] = int(payload.kyc_required)
        if not fields.get("start_token"):
            fields["start_token"] = self.generate_start_token()
        fields["created_at"] = now
        fields["updated_at"] = now
        columns = ", ".join(fields.keys())
        placeholders = ", ".join(["?"] * len(fields))
        values = list(fields.values())
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                f"INSERT INTO orders ({columns}) VALUES ({placeholders})",
                values,
            )
            await db.commit()
            return cursor.lastrowid

    async def update_order(self, order_id: int, **fields: Any) -> None:
        if not fields:
            return
        fields["updated_at"] = datetime.utcnow().isoformat(timespec="seconds")
        assignments = ", ".join(f"{column} = ?" for column in fields.keys())
        values = list(fields.values())
        values.append(order_id)
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                f"UPDATE orders SET {assignments} WHERE order_id = ?",
                values,
            )
            await db.commit()

    async def get_last_order(self, user_id: int) -> Optional[OrderRecord]:
        query = """
            SELECT * FROM orders
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT 1
        """
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(query, (user_id,))
            row = await cursor.fetchone()
        if row is None:
            return None
        return self._row_to_order(row)

    async def get_order(self, order_id: int) -> Optional[OrderRecord]:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM orders WHERE order_id = ? LIMIT 1",
                (order_id,),
            )
            row = await cursor.fetchone()
        if row is None:
            return None
        return self._row_to_order(row)

    async def list_by_status(self, status: str) -> List[OrderRecord]:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM orders WHERE status = ? ORDER BY created_at DESC",
                (status,),
            )
            rows = await cursor.fetchall()
        return [self._row_to_order(row) for row in rows]

    async def list_recent(self, limit: int = 200) -> List[OrderRecord]:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM orders ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
            rows = await cursor.fetchall()
        return [self._row_to_order(row) for row in rows]

    async def get_stats(self) -> Dict[str, int]:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT status, COUNT(*) AS cnt FROM orders GROUP BY status"
            )
            rows = await cursor.fetchall()
        return {row["status"]: row["cnt"] for row in rows}

    async def find_active_for_email(self, email: str, states: Sequence[str]) -> Optional[OrderRecord]:
        if not email:
            return None
        query = """
            SELECT * FROM orders
            WHERE email = ? AND state IN ({states})
            ORDER BY updated_at DESC
            LIMIT 1
        """.format(states=",".join(["?"] * len(states)))
        params: List[Any] = [email, *states]
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(query, params)
            row = await cursor.fetchone()
        if row is None:
            return None
        return self._row_to_order(row)

    async def find_active_for_tg(self, tg_user_id: int, states: Sequence[str]) -> Optional[OrderRecord]:
        query = """
            SELECT * FROM orders
            WHERE tg_user_id = ? AND state IN ({states})
            ORDER BY updated_at DESC
            LIMIT 1
        """.format(states=",".join(["?"] * len(states)))
        params: List[Any] = [tg_user_id, *states]
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(query, params)
            row = await cursor.fetchone()
        if row is None:
            return None
        return self._row_to_order(row)

    async def get_by_start_token(self, token: str) -> Optional[OrderRecord]:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM orders WHERE start_token = ? LIMIT 1",
                (token,),
            )
            row = await cursor.fetchone()
        if row is None:
            return None
        return self._row_to_order(row)

    async def submit_order(self, order_id: int, *, price_eur: Optional[int] = None) -> Optional[OrderRecord]:
        record = await self.get_order(order_id)
        if record is None:
            return None
        if record.state == "submitted":
            return record
        updates: Dict[str, Any] = self._state_fields("submitted")
        if price_eur is not None:
            updates["price_eur"] = price_eur
        await self.update_order(order_id, **updates)
        return await self.get_order(order_id)

    async def update_from_telegram(self, order_id: int, *, tg_user_id: Optional[int], **fields: Any) -> Optional[OrderRecord]:
        updates = dict(fields)
        updates.update(self._state_fields("in_progress"))
        if tg_user_id is not None:
            updates.setdefault("tg_user_id", tg_user_id)
            updates.setdefault("user_id", tg_user_id)
        await self.update_order(order_id, **updates)
        return await self.get_order(order_id)

    async def upsert_draft_order(
        self,
        payload: OrderCreate,
        *,
        match_email: Optional[str] = None,
        match_tg_user_id: Optional[int] = None,
        active_states: Sequence[str] = ("draft", "in_progress"),
    ) -> OrderRecord:
        existing: Optional[OrderRecord] = None
        if match_email:
            existing = await self.find_active_for_email(match_email, active_states)
        if existing is None and match_tg_user_id is not None:
            existing = await self.find_active_for_tg(match_tg_user_id, active_states)
        if existing:
            updates = asdict(payload)
            updates.pop("state", None)
            updates.pop("source", None)
            updates.pop("start_token", None)
            updates["state"] = payload.state
            updates["status"] = payload.state
            await self.update_order(existing.order_id, **updates)
            refreshed = await self.get_order(existing.order_id)
            assert refreshed is not None
            return refreshed
        order_id = await self.create_order(payload)
        new_record = await self.get_order(order_id)
        assert new_record is not None
        return new_record

    async def save_payload_reference(self, token: str, payload: str) -> None:
        now = datetime.utcnow().isoformat(timespec="seconds")
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                """
                INSERT INTO payload_cache(token, payload, created_at)
                VALUES(?, ?, ?)
                ON CONFLICT(token) DO UPDATE SET payload = excluded.payload, created_at = excluded.created_at
                """,
                (token, payload, now),
            )
            await db.commit()

    async def get_payload_reference(self, token: str) -> Optional[str]:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT payload FROM payload_cache WHERE token = ? LIMIT 1",
                (token,),
            )
            row = await cursor.fetchone()
        if row is None:
            return None
        return row["payload"]

    async def delete_payload_reference(self, token: str) -> None:
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "DELETE FROM payload_cache WHERE token = ?",
                (token,),
            )
            await db.commit()

    async def cleanup_payload_references(self, max_age_hours: int = 72) -> int:
        cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                "DELETE FROM payload_cache WHERE created_at < ?",
                (cutoff.isoformat(timespec="seconds"),),
            )
            await db.commit()
            return cursor.rowcount

    async def find_by_payload_hash(self, user_id: int, payload_hash: str) -> Optional[OrderRecord]:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM orders WHERE user_id = ? AND payload_hash = ? ORDER BY created_at DESC LIMIT 1",
                (user_id, payload_hash),
            )
            row = await cursor.fetchone()
        if row is None:
            return None
        return self._row_to_order(row)

    async def set_language(self, user_id: int, language: str) -> None:
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "INSERT INTO user_settings(user_id, language) VALUES (?, ?) "
                "ON CONFLICT(user_id) DO UPDATE SET language = excluded.language",
                (user_id, language),
            )
            await db.commit()

    async def get_language(self, user_id: int) -> Optional[str]:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT language FROM user_settings WHERE user_id = ? LIMIT 1",
                (user_id,),
            )
            row = await cursor.fetchone()
        if row is None:
            return None
        return row["language"]

    def _row_to_order(self, row: aiosqlite.Row) -> OrderRecord:
        return OrderRecord(
            order_id=row["order_id"],
            user_id=row["user_id"],
            username=row["username"],
            source=row["source"],
            state=row["state"],
            start_token=row["start_token"],
            geo=row["geo"],
            method_user_text=row["method_user_text"],
            tests_count=row["tests_count"],
            withdraw_required=bool(row["withdraw_required"]),
            custom_test_required=bool(row["custom_test_required"]),
            custom_test_text=row["custom_test_text"],
            kyc_required=bool(row["kyc_required"]),
            comments=row["comments"],
            site_url=row["site_url"],
            login=row["login"],
            password_enc=row["password_enc"],
            payout_surcharge=row["payout_surcharge"],
            price_eur=row["price_eur"],
            status=row["status"],
            payment_network=row["payment_network"],
            payment_wallet=row["payment_wallet"],
            payment_txid=row["payment_txid"],
            payment_proof_file_id=row["payment_proof_file_id"],
            admin_notes=row["admin_notes"],
            payload_hash=row["payload_hash"],
            tg_user_id=row["tg_user_id"],
            email=row["email"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _state_fields(state: str) -> Dict[str, Any]:
        return {"state": state, "status": state}


def serialize_files(items: Iterable[Dict[str, Any]]) -> str:
    return json.dumps(list(items))
