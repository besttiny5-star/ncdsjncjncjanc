from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

import aiosqlite


@dataclass(slots=True)
class OrderRecord:
    order_id: int
    user_id: int
    username: Optional[str]
    source: str
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
    price_eur: Optional[int]
    status: str
    payment_network: Optional[str]
    payment_wallet: Optional[str]
    payment_txid: Optional[str]
    payment_proof_file_id: Optional[str]
    admin_notes: Optional[str]
    created_at: str
    updated_at: str


@dataclass(slots=True)
class OrderCreate:
    user_id: int
    username: Optional[str]
    source: str
    geo: str
    method_user_text: str
    tests_count: int
    withdraw_required: bool
    custom_test_required: bool
    custom_test_text: Optional[str]
    kyc_required: bool
    comments: Optional[str]
    site_url: Optional[str]
    login: Optional[str]
    password_enc: Optional[str]
    price_eur: int
    status: str
    payment_network: str
    payment_wallet: str


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
                    price_eur INTEGER,
                    status TEXT NOT NULL,
                    payment_network TEXT,
                    payment_wallet TEXT,
                    payment_txid TEXT,
                    payment_proof_file_id TEXT,
                    admin_notes TEXT,
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
            await db.execute("CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at)")
            await db.commit()

    async def create_order(self, payload: OrderCreate) -> int:
        now = datetime.utcnow().isoformat(timespec="seconds")
        fields: Dict[str, Any] = asdict(payload)
        fields["withdraw_required"] = int(payload.withdraw_required)
        fields["custom_test_required"] = int(payload.custom_test_required)
        fields["kyc_required"] = int(payload.kyc_required)
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

    async def list_user_orders(self, user_id: int, limit: int = 5) -> List[OrderRecord]:
        query = """
            SELECT * FROM orders
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
        """
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(query, (user_id, limit))
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
            price_eur=row["price_eur"],
            status=row["status"],
            payment_network=row["payment_network"],
            payment_wallet=row["payment_wallet"],
            payment_txid=row["payment_txid"],
            payment_proof_file_id=row["payment_proof_file_id"],
            admin_notes=row["admin_notes"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


def serialize_files(items: Iterable[Dict[str, Any]]) -> str:
    return json.dumps(list(items))
