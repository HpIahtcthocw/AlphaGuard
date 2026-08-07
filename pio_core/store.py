"""SQLite-backed append-only ledger and paper order state machine."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Dict, Iterable, Mapping, Optional

from portfolio.importers import Holding

from .paper import simulate_fill
from .risk import evaluate_order


SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS accounts (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, base_currency TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS snapshots (
  id TEXT PRIMARY KEY, account_id TEXT NOT NULL, as_of TEXT NOT NULL, source_name TEXT NOT NULL,
  source_hash TEXT NOT NULL, fx_json TEXT NOT NULL, parent_snapshot_id TEXT, created_at TEXT NOT NULL,
  UNIQUE(account_id, source_hash), FOREIGN KEY(account_id) REFERENCES accounts(id)
);
CREATE TABLE IF NOT EXISTS positions (
  id INTEGER PRIMARY KEY AUTOINCREMENT, snapshot_id TEXT NOT NULL, symbol TEXT NOT NULL, name TEXT NOT NULL,
  market TEXT NOT NULL, currency TEXT NOT NULL, quantity TEXT NOT NULL, average_cost TEXT,
  last_price TEXT, market_value TEXT NOT NULL, asset_type TEXT NOT NULL,
  UNIQUE(snapshot_id, symbol, currency), FOREIGN KEY(snapshot_id) REFERENCES snapshots(id)
);
CREATE TABLE IF NOT EXISTS order_intents (
  id TEXT PRIMARY KEY, account_id TEXT NOT NULL, source_snapshot_id TEXT NOT NULL, symbol TEXT NOT NULL,
  market TEXT NOT NULL, currency TEXT NOT NULL, side TEXT NOT NULL, quantity TEXT NOT NULL,
  reference_price TEXT NOT NULL, reason TEXT NOT NULL, status TEXT NOT NULL, idempotency_key TEXT NOT NULL UNIQUE,
  expires_at TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  FOREIGN KEY(account_id) REFERENCES accounts(id), FOREIGN KEY(source_snapshot_id) REFERENCES snapshots(id)
);
CREATE TABLE IF NOT EXISTS risk_checks (
  id INTEGER PRIMARY KEY AUTOINCREMENT, order_intent_id TEXT NOT NULL, code TEXT NOT NULL,
  status TEXT NOT NULL, message TEXT NOT NULL, created_at TEXT NOT NULL,
  FOREIGN KEY(order_intent_id) REFERENCES order_intents(id)
);
CREATE TABLE IF NOT EXISTS approvals (
  id TEXT PRIMARY KEY, order_intent_id TEXT NOT NULL UNIQUE, approved_by TEXT NOT NULL,
  approved_at TEXT NOT NULL, FOREIGN KEY(order_intent_id) REFERENCES order_intents(id)
);
CREATE TABLE IF NOT EXISTS fills (
  id TEXT PRIMARY KEY, order_intent_id TEXT NOT NULL UNIQUE, snapshot_id TEXT NOT NULL,
  fill_price TEXT NOT NULL, quantity TEXT NOT NULL, fee TEXT NOT NULL, currency TEXT NOT NULL,
  filled_at TEXT NOT NULL, FOREIGN KEY(order_intent_id) REFERENCES order_intents(id),
  FOREIGN KEY(snapshot_id) REFERENCES snapshots(id)
);
CREATE TABLE IF NOT EXISTS broker_orders (
  id TEXT PRIMARY KEY, order_intent_id TEXT NOT NULL UNIQUE, broker TEXT NOT NULL,
  environment TEXT NOT NULL, external_order_id TEXT NOT NULL UNIQUE, status TEXT NOT NULL,
  payload_json TEXT NOT NULL, submitted_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  FOREIGN KEY(order_intent_id) REFERENCES order_intents(id)
);
CREATE TABLE IF NOT EXISTS audit_log (
  sequence INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT NOT NULL UNIQUE, event_type TEXT NOT NULL,
  entity_type TEXT NOT NULL, entity_id TEXT NOT NULL, payload_json TEXT NOT NULL,
  previous_hash TEXT NOT NULL, event_hash TEXT NOT NULL, created_at TEXT NOT NULL
);
"""


class PioStore:
    def __init__(self, path: str):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(SCHEMA)

    def ensure_account(self, account_id: str = "default", name: str = "我的投资账户", base_currency: str = "CNY") -> str:
        now = _now()
        with self._connect() as connection:
            cursor = connection.execute("INSERT OR IGNORE INTO accounts(id,name,base_currency,created_at) VALUES(?,?,?,?)", (account_id, name, base_currency, now))
            if cursor.rowcount:
                self._audit(connection, "ACCOUNT_READY", "account", account_id, {"name": name, "base_currency": base_currency})
        return account_id

    def import_holdings(
        self,
        holdings: Iterable[Holding],
        fx_rates: Mapping[str, Decimal],
        source_name: str,
        as_of: str,
        account_id: str = "default",
    ) -> Dict[str, object]:
        self.ensure_account(account_id)
        records = list(holdings)
        payload = {"as_of": as_of, "source": source_name, "fx": {k: str(v) for k, v in sorted(fx_rates.items())}, "holdings": [_holding_dict(item) for item in records]}
        source_hash = _hash_json(payload)
        now = _now()
        with self._connect() as connection:
            existing = connection.execute("SELECT id FROM snapshots WHERE account_id=? AND source_hash=?", (account_id, source_hash)).fetchone()
            if existing:
                return {"snapshot_id": existing["id"], "idempotent": True, "positions": len(records)}
            snapshot_id = str(uuid.uuid4())
            connection.execute(
                "INSERT INTO snapshots(id,account_id,as_of,source_name,source_hash,fx_json,parent_snapshot_id,created_at) VALUES(?,?,?,?,?,?,?,?)",
                (snapshot_id, account_id, as_of, source_name, source_hash, _canonical({k: str(v) for k, v in fx_rates.items()}), None, now),
            )
            self._insert_positions(connection, snapshot_id, [_holding_dict(item) for item in records])
            self._audit(connection, "HOLDINGS_IMPORTED", "snapshot", snapshot_id, {"account_id": account_id, "positions": len(records), "source_hash": source_hash})
        return {"snapshot_id": snapshot_id, "idempotent": False, "positions": len(records)}

    def portfolio(self, account_id: str = "default") -> Dict[str, object]:
        with self._connect() as connection:
            snapshot = connection.execute("SELECT * FROM snapshots WHERE account_id=? ORDER BY created_at DESC, rowid DESC LIMIT 1", (account_id,)).fetchone()
            if not snapshot:
                return {"account_id": account_id, "snapshot_id": None, "positions": [], "total_base_value": "0", "base_currency": "CNY"}
            positions = [dict(row) for row in connection.execute("SELECT symbol,name,market,currency,quantity,average_cost,last_price,market_value,asset_type FROM positions WHERE snapshot_id=? ORDER BY asset_type,symbol", (snapshot["id"],))]
            fx = {key: Decimal(value) for key, value in json.loads(snapshot["fx_json"]).items()}
            total = sum((_convert(Decimal(item["market_value"]), item["currency"], fx) for item in positions), Decimal("0"))
            return {"account_id": account_id, "snapshot_id": snapshot["id"], "as_of": snapshot["as_of"], "source_name": snapshot["source_name"], "fx_rates": {k: str(v) for k, v in fx.items()}, "positions": positions, "total_base_value": str(total), "base_currency": "CNY"}

    def create_order_intent(
        self,
        symbol: str,
        market: str,
        currency: str,
        side: str,
        quantity: Decimal,
        reference_price: Decimal,
        reason: str,
        idempotency_key: str,
        account_id: str = "default",
        expires_at: Optional[str] = None,
    ) -> Dict[str, object]:
        if len(reason.strip()) < 8:
            raise ValueError("order intent requires a meaningful reason")
        with self._connect() as connection:
            existing = connection.execute("SELECT id FROM order_intents WHERE idempotency_key=?", (idempotency_key,)).fetchone()
        if existing:
            return self.order_intent(existing["id"])
        current = self.portfolio(account_id)
        if not current["snapshot_id"]:
            raise ValueError("account has no holdings snapshot")
        fx = {key: Decimal(value) for key, value in current["fx_rates"].items()}
        decision = evaluate_order(current["positions"], fx, str(current["as_of"]), symbol, market, currency, side, quantity, reference_price)
        now = _now()
        with self._connect() as connection:
            intent_id = str(uuid.uuid4())
            status = "PENDING_APPROVAL" if decision.status == "PASS" else "REJECTED"
            connection.execute(
                "INSERT INTO order_intents(id,account_id,source_snapshot_id,symbol,market,currency,side,quantity,reference_price,reason,status,idempotency_key,expires_at,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (intent_id, account_id, current["snapshot_id"], symbol, market, currency, side.upper(), str(quantity), str(reference_price), reason.strip(), status, idempotency_key, expires_at, now, now),
            )
            for check in decision.checks:
                connection.execute("INSERT INTO risk_checks(order_intent_id,code,status,message,created_at) VALUES(?,?,?,?,?)", (intent_id, check.code, check.status, check.message, now))
            self._audit(connection, "ORDER_INTENT_CREATED", "order_intent", intent_id, {"status": status, "symbol": symbol, "side": side.upper(), "quantity": str(quantity), "checks": [check.__dict__ for check in decision.checks]})
        return self.order_intent(intent_id)

    def approve(self, intent_id: str, approved_by: str) -> Dict[str, object]:
        with self._connect() as connection:
            intent = connection.execute("SELECT * FROM order_intents WHERE id=?", (intent_id,)).fetchone()
            if not intent:
                raise ValueError("order intent not found")
            if intent["status"] != "PENDING_APPROVAL":
                raise ValueError(f"cannot approve order in status {intent['status']}")
            if intent["expires_at"] and datetime.fromisoformat(intent["expires_at"].replace("Z", "+00:00")) < datetime.now(timezone.utc):
                raise ValueError("order intent has expired")
            now = _now()
            connection.execute("INSERT INTO approvals(id,order_intent_id,approved_by,approved_at) VALUES(?,?,?,?)", (str(uuid.uuid4()), intent_id, approved_by, now))
            connection.execute("UPDATE order_intents SET status='APPROVED',updated_at=? WHERE id=?", (now, intent_id))
            self._audit(connection, "ORDER_APPROVED", "order_intent", intent_id, {"approved_by": approved_by})
        return self.order_intent(intent_id)

    def simulate(self, intent_id: str) -> Dict[str, object]:
        with self._connect() as connection:
            intent = connection.execute("SELECT * FROM order_intents WHERE id=?", (intent_id,)).fetchone()
            if not intent:
                raise ValueError("order intent not found")
            if intent["status"] != "APPROVED":
                raise ValueError(f"cannot execute order in status {intent['status']}")
            if intent["expires_at"] and datetime.fromisoformat(intent["expires_at"].replace("Z", "+00:00")) < datetime.now(timezone.utc):
                raise ValueError("order intent has expired")
            latest = connection.execute("SELECT id FROM snapshots WHERE account_id=? ORDER BY created_at DESC, rowid DESC LIMIT 1", (intent["account_id"],)).fetchone()
            if not latest or latest["id"] != intent["source_snapshot_id"]:
                raise ValueError("portfolio changed after risk approval; create a new order intent")
            source = connection.execute("SELECT * FROM snapshots WHERE id=?", (intent["source_snapshot_id"],)).fetchone()
            positions = [dict(row) for row in connection.execute("SELECT symbol,name,market,currency,quantity,average_cost,last_price,market_value,asset_type FROM positions WHERE snapshot_id=?", (source["id"],))]
            fill = simulate_fill(intent["side"], Decimal(intent["quantity"]), Decimal(intent["reference_price"]))
            updated = _apply_fill(positions, dict(intent), fill.fill_price, fill.quantity, fill.fee)
            now = _now()
            snapshot_id = str(uuid.uuid4())
            payload = {"parent": source["id"], "intent": intent_id, "fill_price": str(fill.fill_price), "quantity": str(fill.quantity), "fee": str(fill.fee)}
            connection.execute(
                "INSERT INTO snapshots(id,account_id,as_of,source_name,source_hash,fx_json,parent_snapshot_id,created_at) VALUES(?,?,?,?,?,?,?,?)",
                (snapshot_id, intent["account_id"], now, f"paper-fill:{intent_id}", _hash_json(payload), source["fx_json"], source["id"], now),
            )
            self._insert_positions(connection, snapshot_id, updated)
            fill_id = str(uuid.uuid4())
            connection.execute("INSERT INTO fills(id,order_intent_id,snapshot_id,fill_price,quantity,fee,currency,filled_at) VALUES(?,?,?,?,?,?,?,?)", (fill_id, intent_id, snapshot_id, str(fill.fill_price), str(fill.quantity), str(fill.fee), intent["currency"], now))
            connection.execute("UPDATE order_intents SET status='FILLED',updated_at=? WHERE id=?", (now, intent_id))
            self._audit(connection, "PAPER_FILL_CREATED", "fill", fill_id, {**payload, "snapshot_id": snapshot_id})
        return {"order": self.order_intent(intent_id), "fill": {"id": fill_id, "snapshot_id": snapshot_id, "fill_price": str(fill.fill_price), "quantity": str(fill.quantity), "fee": str(fill.fee)}, "portfolio": self.portfolio(intent["account_id"])}

    def prepare_external_execution(self, intent_id: str) -> Dict[str, object]:
        with self._connect() as connection:
            intent = connection.execute("SELECT * FROM order_intents WHERE id=?", (intent_id,)).fetchone()
            if not intent:
                raise ValueError("order intent not found")
            if intent["status"] == "SUBMITTED":
                existing = connection.execute("SELECT * FROM broker_orders WHERE order_intent_id=?", (intent_id,)).fetchone()
                if existing:
                    result = dict(intent)
                    result["existing_broker_order"] = dict(existing)
                    return result
            if intent["status"] != "APPROVED":
                raise ValueError(f"cannot submit order in status {intent['status']}")
            latest = connection.execute("SELECT id FROM snapshots WHERE account_id=? ORDER BY created_at DESC, rowid DESC LIMIT 1", (intent["account_id"],)).fetchone()
            if not latest or latest["id"] != intent["source_snapshot_id"]:
                raise ValueError("portfolio changed after risk approval; create a new order intent")
            return dict(intent)

    def record_broker_submission(
        self,
        intent_id: str,
        broker: str,
        environment: str,
        external_order_id: str,
        status: str,
        payload: Mapping[str, object],
        submitted_at: Optional[str] = None,
    ) -> Dict[str, object]:
        now = _now()
        with self._connect() as connection:
            existing = connection.execute("SELECT * FROM broker_orders WHERE order_intent_id=?", (intent_id,)).fetchone()
            if existing:
                return dict(existing)
            intent = connection.execute("SELECT status FROM order_intents WHERE id=?", (intent_id,)).fetchone()
            if not intent or intent["status"] != "APPROVED":
                raise ValueError("broker submission requires an approved order intent")
            broker_order_id = str(uuid.uuid4())
            connection.execute(
                "INSERT INTO broker_orders(id,order_intent_id,broker,environment,external_order_id,status,payload_json,submitted_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
                (broker_order_id, intent_id, broker, environment, external_order_id, status, _canonical(payload), submitted_at or now, now),
            )
            connection.execute("UPDATE order_intents SET status='SUBMITTED',updated_at=? WHERE id=?", (now, intent_id))
            self._audit(connection, "BROKER_ORDER_SUBMITTED", "broker_order", broker_order_id, {"intent_id": intent_id, "broker": broker, "environment": environment, "external_order_id": external_order_id, "status": status})
            return dict(connection.execute("SELECT * FROM broker_orders WHERE id=?", (broker_order_id,)).fetchone())

    def order_intent(self, intent_id: str) -> Dict[str, object]:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM order_intents WHERE id=?", (intent_id,)).fetchone()
            if not row:
                raise ValueError("order intent not found")
            result = dict(row)
            result["risk_checks"] = [dict(item) for item in connection.execute("SELECT code,status,message FROM risk_checks WHERE order_intent_id=? ORDER BY id", (intent_id,))]
            approval = connection.execute("SELECT approved_by,approved_at FROM approvals WHERE order_intent_id=?", (intent_id,)).fetchone()
            result["approval"] = dict(approval) if approval else None
            broker_order = connection.execute("SELECT id,broker,environment,external_order_id,status,submitted_at,updated_at FROM broker_orders WHERE order_intent_id=?", (intent_id,)).fetchone()
            result["broker_order"] = dict(broker_order) if broker_order else None
            return result

    def audit_events(self, limit: int = 100) -> Dict[str, object]:
        with self._connect() as connection:
            events = [dict(row) for row in connection.execute("SELECT * FROM audit_log ORDER BY sequence DESC LIMIT ?", (limit,))]
            verified = self._verify_audit(connection)
        return {"verified": verified, "events": events}

    def _insert_positions(self, connection: sqlite3.Connection, snapshot_id: str, positions: Iterable[Mapping[str, object]]) -> None:
        connection.executemany(
            "INSERT INTO positions(snapshot_id,symbol,name,market,currency,quantity,average_cost,last_price,market_value,asset_type) VALUES(?,?,?,?,?,?,?,?,?,?)",
            [(snapshot_id, item["symbol"], item["name"], item["market"], item["currency"], str(item["quantity"]), _optional(item.get("average_cost")), _optional(item.get("last_price")), str(item["market_value"]), item["asset_type"]) for item in positions],
        )

    def _audit(self, connection: sqlite3.Connection, event_type: str, entity_type: str, entity_id: str, payload: Mapping[str, object]) -> None:
        previous = connection.execute("SELECT event_hash FROM audit_log ORDER BY sequence DESC LIMIT 1").fetchone()
        previous_hash = previous["event_hash"] if previous else "GENESIS"
        event_id = str(uuid.uuid4())
        created_at = _now()
        payload_json = _canonical(payload)
        event_hash = hashlib.sha256(f"{previous_hash}|{event_id}|{event_type}|{entity_type}|{entity_id}|{payload_json}|{created_at}".encode()).hexdigest()
        connection.execute("INSERT INTO audit_log(event_id,event_type,entity_type,entity_id,payload_json,previous_hash,event_hash,created_at) VALUES(?,?,?,?,?,?,?,?)", (event_id, event_type, entity_type, entity_id, payload_json, previous_hash, event_hash, created_at))

    def _verify_audit(self, connection: sqlite3.Connection) -> bool:
        previous_hash = "GENESIS"
        for row in connection.execute("SELECT * FROM audit_log ORDER BY sequence"):
            expected = hashlib.sha256(f"{previous_hash}|{row['event_id']}|{row['event_type']}|{row['entity_type']}|{row['entity_id']}|{row['payload_json']}|{row['created_at']}".encode()).hexdigest()
            if row["previous_hash"] != previous_hash or row["event_hash"] != expected:
                return False
            previous_hash = row["event_hash"]
        return True

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection


def _apply_fill(positions, intent, fill_price: Decimal, quantity: Decimal, fee: Decimal):
    rows = {f"{item['symbol']}|{item['currency']}": dict(item) for item in positions}
    key = f"{intent['symbol']}|{intent['currency']}"
    current = rows.get(key, {"symbol": intent["symbol"], "name": intent["symbol"], "market": intent["market"], "currency": intent["currency"], "quantity": "0", "average_cost": None, "last_price": None, "market_value": "0", "asset_type": "STOCK"})
    old_quantity = Decimal(str(current["quantity"]))
    new_quantity = old_quantity + quantity if intent["side"] == "BUY" else old_quantity - quantity
    if new_quantity < 0:
        raise ValueError("paper fill would create a short position")
    current["quantity"] = str(new_quantity)
    if intent["side"] == "BUY" and new_quantity > 0:
        old_average = Decimal(str(current["average_cost"] or current["last_price"] or fill_price))
        current["average_cost"] = str((old_quantity * old_average + quantity * fill_price + fee) / new_quantity)
    current["last_price"] = str(fill_price)
    current["market_value"] = str(new_quantity * fill_price)
    rows[key] = current
    cash_key = f"CASH_{intent['currency']}|{intent['currency']}"
    cash = rows.get(cash_key, {"symbol": f"CASH_{intent['currency']}", "name": f"{intent['currency']} 现金", "market": intent["market"], "currency": intent["currency"], "quantity": "0", "average_cost": "1", "last_price": "1", "market_value": "0", "asset_type": "CASH"})
    cash_change = quantity * fill_price + fee
    cash_value = Decimal(str(cash["market_value"])) - cash_change if intent["side"] == "BUY" else Decimal(str(cash["market_value"])) + quantity * fill_price - fee
    if cash_value < 0:
        raise ValueError("paper fill would create negative cash")
    cash["quantity"] = str(cash_value)
    cash["market_value"] = str(cash_value)
    rows[cash_key] = cash
    return [item for item in rows.values() if Decimal(str(item["quantity"])) != 0 or item["asset_type"] == "CASH"]


def _holding_dict(item: Holding) -> Dict[str, object]:
    return {"symbol": item.symbol, "name": item.name, "market": item.market, "currency": item.currency, "quantity": item.quantity, "average_cost": item.average_cost, "last_price": item.last_price, "market_value": item.market_value, "asset_type": item.asset_type}


def _convert(value: Decimal, currency: str, fx_rates: Mapping[str, Decimal]) -> Decimal:
    return value if currency == "CNY" else value * fx_rates[f"{currency}/CNY"]


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _hash_json(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


def _optional(value: object) -> Optional[str]:
    return None if value is None else str(value)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
