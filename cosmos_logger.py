"""Optional Cosmos DB audit logger for agent decisions."""
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

_executor = ThreadPoolExecutor(max_workers=2)


class CosmosLogger:
    def __init__(self):
        self.client = None
        self.container = None
        conn_str = os.getenv("COSMOS_CONNECTION_STRING")
        if conn_str:
            try:
                from azure.cosmos import CosmosClient
                self.client = CosmosClient.from_connection_string(conn_str)
                db = self.client.get_database_client("pripyat-db")
                self.container = db.get_container_client("decisions")
            except Exception:
                pass

    @property
    def available(self) -> bool:
        return self.container is not None

    def log_decision(self, agent_id: str, tick: int, sim_time: str, decision: dict):
        if not self.available:
            return
        doc = {
            "id": f"{tick}_{agent_id}_{datetime.utcnow().isoformat()}",
            "agent_id": agent_id,
            "tick": tick,
            "sim_time": sim_time,
            "decision": decision,
            "logged_at": datetime.utcnow().isoformat(),
        }
        # Fire-and-forget in a thread — keeps the asyncio event loop unblocked
        # so LLM async responses can be received without timeout
        _executor.submit(self._upsert, doc)

    def _upsert(self, doc: dict):
        try:
            self.container.upsert_item(doc)
        except Exception:
            pass