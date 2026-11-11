"""Tier 4: PostgreSQL + Apache AGE Knowledge Graph Store Adapter (OSI Default).

Replaces SSPL/BSL graph engines in default deployments with open-source
PostgreSQL + Apache AGE (Apache-2.0) while preserving a deterministic
NetworkX in-memory fallback for hermetic offline testing.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from memory.core.exceptions import AdapterConnectionError
from memory.core.interfaces import BaseGraphStore
from memory.tiers.graph._nx_fallback import NetworkXGraphFallback, utc_now_str


def _cypher_literal(value: Any) -> str:
    """Format a Python value as an inline Apache AGE Cypher literal."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (dict, list)):
        text = json.dumps(value, sort_keys=True)
    else:
        text = str(value)
    escaped = (
        text.replace("\\", "\\\\")
        .replace("'", "\\'")
        .replace("$$", "$ $")
    )
    return f"'{escaped}'"


def _substitute_cypher_params(query: str, params: Dict[str, Any]) -> str:
    """Substitute $param placeholders with inline Cypher literals for AGE $$ blocks."""
    if not params:
        return query
    pattern = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)")
    return pattern.sub(
        lambda m: _cypher_literal(params[m.group(1)]) if m.group(1) in params else m.group(0),
        query,
    )


def _split_top_level_commas(expr_list: str) -> List[str]:
    """Split a RETURN clause expression list on top-level commas."""
    parts: List[str] = []
    current: List[str] = []
    depth = 0
    in_single = False
    in_double = False
    escape = False

    for ch in expr_list:
        if escape:
            current.append(ch)
            escape = False
            continue
        if ch == "\\" and (in_single or in_double):
            current.append(ch)
            escape = True
            continue
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif not in_single and not in_double:
            if ch in "([{":
                depth += 1
            elif ch in ")]}" and depth > 0:
                depth -= 1
            elif ch == "," and depth == 0:
                part = "".join(current).strip()
                if part:
                    parts.append(part)
                current = []
                continue
        current.append(ch)

    tail = "".join(current).strip()
    if tail:
        parts.append(tail)
    return parts


def _infer_return_keys(cypher_query: str) -> List[str]:
    """Extract ordered result keys from a Cypher RETURN clause."""
    matches = list(re.finditer(r"\bRETURN\b", cypher_query, re.IGNORECASE))
    if not matches:
        return ["result"]
    tail = cypher_query[matches[-1].end() :].strip().rstrip(";")
    # Trim trailing ORDER BY / SKIP / LIMIT clauses when present.
    tail = re.split(r"\b(?:ORDER\s+BY|SKIP|LIMIT)\b", tail, maxsplit=1, flags=re.IGNORECASE)[0].strip()
    if not tail:
        return ["result"]

    keys: List[str] = []
    for item in _split_top_level_commas(tail):
        alias_match = re.search(r"\bAS\s+([A-Za-z_][A-Za-z0-9_]*)\s*$", item, re.IGNORECASE)
        if alias_match:
            keys.append(alias_match.group(1))
        else:
            keys.append(item.strip())
    return keys or ["result"]


def _parse_agtype(raw: Any) -> Any:
    """Decode an Apache AGE agtype value into standard Python primitives/dicts."""
    if raw is None or not isinstance(raw, str):
        return raw
    cleaned = re.sub(r"::(vertex|edge|path|numeric|integer|float|boolean)\b", "", raw).strip()
    if not cleaned:
        return cleaned
    try:
        return json.loads(cleaned)
    except Exception:
        return cleaned


class ApacheAGEAdapter(BaseGraphStore):
    """Graph store powered by PostgreSQL + Apache AGE, with NetworkX fallback."""

    def __init__(
        self,
        postgres_url: Optional[str] = None,
        graph_name: str = "ci_memory_graph",
        auto_fallback: bool = True,
    ) -> None:
        self._postgres_url = (
            postgres_url
            if postgres_url is not None
            else (
                os.getenv("AGE_POSTGRES_URL")
                or os.getenv("POSTGRES_URL")
                or "postgresql://postgres:postgres@localhost:5433/postgres"
            )
        )
        self._graph_name = re.sub(r"[^A-Za-z0-9_]", "_", graph_name.strip()) or "ci_memory_graph"
        self._auto_fallback = auto_fallback
        self._is_in_memory = False
        self._conn: Optional[Any] = None

        self._fallback = NetworkXGraphFallback()
        self._nx_graph = self._fallback.graph

        self._init_client()

    @staticmethod
    def _parse_pg_url(url: str) -> Dict[str, Any]:
        parsed = urlparse(url)
        return {
            "host": parsed.hostname or "localhost",
            "port": parsed.port or 5432,
            "user": parsed.username or "postgres",
            "password": parsed.password or "postgres",
            "database": (parsed.path or "/postgres").lstrip("/") or "postgres",
            "timeout": 3,
        }

    def _init_client(self) -> None:
        if not self._postgres_url or self._postgres_url == ":memory:":
            self._is_in_memory = True
            return

        try:
            import pg8000.dbapi

            kwargs = self._parse_pg_url(self._postgres_url)
            conn = pg8000.dbapi.connect(**kwargs)
            cur = conn.cursor()
            cur.execute("CREATE EXTENSION IF NOT EXISTS age;")
            cur.execute("LOAD 'age';")
            cur.execute('SET search_path = ag_catalog, "$user", public;')
            cur.execute("SELECT 1 FROM ag_catalog.ag_graph WHERE name = %s;", (self._graph_name,))
            if cur.fetchone() is None:
                cur.execute("SELECT create_graph(%s);", (self._graph_name,))
            conn.commit()
            cur.close()
            self._conn = conn
            self._is_in_memory = False
        except Exception as exc:
            if self._conn is not None:
                try:
                    self._conn.close()
                except Exception:
                    pass
                self._conn = None
            if self._auto_fallback:
                self._is_in_memory = True
            else:
                raise AdapterConnectionError(
                    f"Failed to initialize Apache AGE connection ({self._postgres_url}): {exc}"
                )

    @property
    def is_in_memory(self) -> bool:
        return self._is_in_memory

    @property
    def graph_name(self) -> str:
        return self._graph_name

    def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None

    def _run_age_cypher(
        self,
        cypher: str,
        params: Optional[Dict[str, Any]] = None,
        return_keys: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        if not self._conn:
            raise AdapterConnectionError("Apache AGE connection is not open.")

        inlined = _substitute_cypher_params(cypher.strip().rstrip(";"), params or {})
        keys = return_keys or _infer_return_keys(inlined)
        col_defs = ", ".join(f"c{idx} agtype" for idx in range(len(keys)))
        sql = f"SELECT * FROM ag_catalog.cypher('{self._graph_name}', $${inlined}$$) AS ({col_defs});"

        cur = self._conn.cursor()
        try:
            cur.execute("LOAD 'age';")
            cur.execute('SET search_path = ag_catalog, "$user", public;')
            cur.execute(sql)
            rows = cur.fetchall() if cur.description else []
            self._conn.commit()
        except Exception:
            try:
                self._conn.rollback()
            except Exception:
                pass
            raise
        finally:
            cur.close()

        output: List[Dict[str, Any]] = []
        for row in rows:
            output.append({keys[idx]: _parse_agtype(row[idx]) for idx in range(len(keys))})
        return output

    def check_health(self) -> bool:
        """Check whether Apache AGE (or hermetic fallback) is healthy."""
        if self._is_in_memory:
            return True
        try:
            rows = self._run_age_cypher("RETURN 1 AS health", return_keys=["health"])
            return len(rows) > 0 and rows[0].get("health") == 1
        except Exception:
            return False

    def add_entity(
        self,
        user_id: str,
        name: str,
        entity_type: str = "Entity",
        properties: Optional[Dict[str, Any]] = None,
        project_id: str = "default",
    ) -> str:
        """Create or update an entity vertex in Apache AGE and local fallback cache."""
        self._fallback.add_entity(
            user_id=user_id,
            name=name,
            entity_type=entity_type,
            properties=properties,
            project_id=project_id,
        )

        if not self._is_in_memory and self._conn:
            clean_type = re.sub(r"[^A-Za-z0-9_]", "", entity_type) or "Entity"
            now = utc_now_str()
            props_json = json.dumps(properties or {}, sort_keys=True)
            params = {
                "name": name,
                "user_id": user_id,
                "project_id": project_id,
                "entity_type": entity_type,
                "now": now,
                "props_json": props_json,
            }
            match_cypher = (
                "MATCH (n {name: $name, user_id: $user_id, project_id: $project_id}) "
                "SET n.updated_at = $now, n.props_json = $props_json "
                "RETURN n.name AS name"
            )
            create_cypher = (
                f"CREATE (n:{clean_type} {{name: $name, user_id: $user_id, project_id: $project_id, "
                "entity_type: $entity_type, created_at: $now, updated_at: $now, props_json: $props_json}) "
                "RETURN n.name AS name"
            )
            try:
                existing = self._run_age_cypher(match_cypher, params=params, return_keys=["name"])
                if not existing:
                    self._run_age_cypher(create_cypher, params=params, return_keys=["name"])
            except Exception as exc:
                if not self._auto_fallback:
                    raise AdapterConnectionError(f"Apache AGE add_entity failed: {exc}")

        return name

    def add_relationship(
        self,
        user_id: str,
        source: str,
        relation: str,
        target: str,
        properties: Optional[Dict[str, Any]] = None,
        project_id: str = "default",
    ) -> Dict[str, Any]:
        """Create or update a directed relationship edge in Apache AGE and fallback cache."""
        src_nid = self._fallback.node_id(user_id, source, project_id)
        tgt_nid = self._fallback.node_id(user_id, target, project_id)
        if src_nid not in self._fallback.graph:
            self.add_entity(user_id=user_id, name=source, project_id=project_id)
        if tgt_nid not in self._fallback.graph:
            self.add_entity(user_id=user_id, name=target, project_id=project_id)

        res = self._fallback.add_relationship(
            user_id=user_id,
            source=source,
            relation=relation,
            target=target,
            properties=properties,
            project_id=project_id,
        )

        if not self._is_in_memory and self._conn:
            now = utc_now_str()
            props_json = json.dumps(properties or {}, sort_keys=True)
            cypher = (
                "MATCH (s {name: $source, user_id: $user_id, project_id: $project_id}) "
                "MATCH (t {name: $target, user_id: $user_id, project_id: $project_id}) "
                f"MERGE (s)-[r:{res['relation']}]->(t) "
                "SET r.updated_at = $now, r.is_active = true, r.props_json = $props_json "
                "RETURN s.name AS source, type(r) AS relation, t.name AS target"
            )
            try:
                self._run_age_cypher(
                    cypher,
                    params={
                        "source": source,
                        "target": target,
                        "user_id": user_id,
                        "project_id": project_id,
                        "now": now,
                        "props_json": props_json,
                    },
                    return_keys=["source", "relation", "target"],
                )
            except Exception as exc:
                if not self._auto_fallback:
                    raise AdapterConnectionError(f"Apache AGE add_relationship failed: {exc}")

        return res

    def delete_relationship(
        self,
        user_id: str,
        source: str,
        relation: str,
        target: str,
        project_id: Optional[str] = None,
    ) -> bool:
        """Delete a directed relationship edge."""
        removed = self._fallback.delete_relationship(
            user_id=user_id,
            source=source,
            relation=relation,
            target=target,
            project_id=project_id,
        )

        if not self._is_in_memory and self._conn:
            pid = project_id or "default"
            rel_clean = re.sub(r"[^A-Za-z0-9_]", "_", relation.strip().upper())
            cypher = (
                f"MATCH (s {{name: $source, user_id: $user_id, project_id: $project_id}})"
                f"-[r:{rel_clean}]->"
                f"(t {{name: $target, user_id: $user_id, project_id: $project_id}}) "
                "DELETE r RETURN 1 AS deleted"
            )
            try:
                rows = self._run_age_cypher(
                    cypher,
                    params={"source": source, "target": target, "user_id": user_id, "project_id": pid},
                    return_keys=["deleted"],
                )
                if len(rows) > 0:
                    removed = True
            except Exception as exc:
                if not self._auto_fallback:
                    raise AdapterConnectionError(f"Apache AGE delete_relationship failed: {exc}")

        return removed

    def multi_hop_query(
        self,
        user_id: str,
        start_entity: str,
        relation: Optional[str] = None,
        hops: int = 2,
        project_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Execute bounded multi-hop BFS traversal from start_entity."""
        if not self._is_in_memory and self._conn:
            pid = project_id or "default"
            rel_clause = (
                f":{re.sub(r'[^A-Za-z0-9_]', '_', relation.strip().upper())}"
                if relation
                else ""
            )
            # Collect direct edges and hydrate local BFS cache for deterministic depth paths.
            cypher = (
                f"MATCH (a {{user_id: $user_id, project_id: $project_id}})"
                f"-[r{rel_clause}]->"
                f"(b {{user_id: $user_id, project_id: $project_id}}) "
                "RETURN a.name AS source, type(r) AS relation, b.name AS target"
            )
            try:
                rows = self._run_age_cypher(
                    cypher,
                    params={"user_id": user_id, "project_id": pid},
                    return_keys=["source", "relation", "target"],
                )
                for row in rows:
                    if row.get("source") and row.get("relation") and row.get("target"):
                        self._fallback.add_relationship(
                            user_id=user_id,
                            source=str(row["source"]),
                            relation=str(row["relation"]),
                            target=str(row["target"]),
                            project_id=pid,
                        )
            except Exception as exc:
                if not self._auto_fallback:
                    raise AdapterConnectionError(f"Apache AGE multi_hop_query failed: {exc}")

        return self._fallback.multi_hop_query(
            user_id=user_id,
            start_entity=start_entity,
            relation=relation,
            hops=hops,
            project_id=project_id,
        )

    def execute_query(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Execute Cypher via Apache AGE SQL wrapper, or in-memory emulation."""
        params = params or {}
        if not self._is_in_memory and self._conn:
            try:
                return self._run_age_cypher(query, params=params)
            except Exception as exc:
                if not self._auto_fallback:
                    raise AdapterConnectionError(f"Apache AGE query failed: {exc}")

        return self._fallback.emulate_cypher(query, params)

    def delete_by_user(self, user_id: str) -> int:
        """Purge all graph vertices and edges owned by user_id."""
        removed = self._fallback.delete_by_user(user_id)
        if not self._is_in_memory and self._conn:
            cypher = "MATCH (n {user_id: $user_id}) DETACH DELETE n RETURN count(*) AS deleted"
            try:
                rows = self._run_age_cypher(
                    cypher,
                    params={"user_id": user_id},
                    return_keys=["deleted"],
                )
                if rows and isinstance(rows[0].get("deleted"), int):
                    removed = max(removed, rows[0]["deleted"])
            except Exception:
                pass
        return removed
