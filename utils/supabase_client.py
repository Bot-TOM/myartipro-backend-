import os
import httpx
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")


class SupabaseDB:
    """Client Supabase REST léger — async, compatible clés sb_* et eyJ*."""

    def __init__(self, url: str, key: str):
        self.base_url = f"{url}/rest/v1"
        self.headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    def table(self, name: str) -> "TableQuery":
        return TableQuery(self.base_url, self.headers, name)


class TableQuery:
    def __init__(self, base_url: str, headers: dict, table: str):
        self.url = f"{base_url}/{table}"
        self.headers = headers.copy()
        self._params: dict = {}
        self._method = "GET"
        self._body = None
        self._single = False

    def select(self, columns: str = "*", *, count: str = None, head: bool = False) -> "TableQuery":
        self._params["select"] = columns
        if count:
            self.headers["Prefer"] = f"count={count}"
        if head:
            self._method = "HEAD"
        return self

    def insert(self, data) -> "TableQuery":
        self._method = "POST"
        self._body = data
        return self

    def update(self, data) -> "TableQuery":
        self._method = "PATCH"
        self._body = data
        return self

    def delete(self) -> "TableQuery":
        self._method = "DELETE"
        return self

    def eq(self, column: str, value) -> "TableQuery":
        self._params[column] = f"eq.{value}"
        return self

    def like(self, column: str, pattern: str) -> "TableQuery":
        self._params[column] = f"like.{pattern}"
        return self

    def lt(self, column: str, value) -> "TableQuery":
        self._params[column] = f"lt.{value}"
        return self

    def gt(self, column: str, value) -> "TableQuery":
        self._params[column] = f"gt.{value}"
        return self

    def is_(self, column: str, value) -> "TableQuery":
        self._params[column] = f"is.{value}"
        return self

    def order(self, column: str, *, desc: bool = False, nullsfirst: bool = True) -> "TableQuery":
        direction = "desc" if desc else "asc"
        nulls = "nullsfirst" if nullsfirst else "nullslast"
        new_order = f"{column}.{direction}.{nulls}"
        if "order" in self._params:
            self._params["order"] = f"{self._params['order']},{new_order}"
        else:
            self._params["order"] = new_order
        return self

    def limit(self, count: int) -> "TableQuery":
        self._params["limit"] = str(count)
        return self

    def single(self) -> "TableQuery":
        self._single = True
        self.headers["Accept"] = "application/vnd.pgrst.object+json"
        return self

    async def execute(self) -> "_Result":
        async with httpx.AsyncClient(verify=True, timeout=10) as client:
            if self._method == "GET":
                resp = await client.get(self.url, headers=self.headers, params=self._params)
            elif self._method == "HEAD":
                resp = await client.head(self.url, headers=self.headers, params=self._params)
                count = resp.headers.get("content-range", "").split("/")[-1]
                return _Result(data=[], count=int(count) if count and count != "*" else 0)
            elif self._method == "POST":
                resp = await client.post(self.url, headers=self.headers, params=self._params, json=self._body)
            elif self._method == "PATCH":
                resp = await client.patch(self.url, headers=self.headers, params=self._params, json=self._body)
            elif self._method == "DELETE":
                resp = await client.delete(self.url, headers=self.headers, params=self._params)
            else:
                raise ValueError(f"Unknown method: {self._method}")

        if resp.status_code >= 400:
            raise Exception(f"Supabase error {resp.status_code}: {resp.text}")

        data = resp.json() if resp.text else []
        if self._single and isinstance(data, list):
            data = data[0] if data else None

        return _Result(data=data)


class _Result:
    def __init__(self, data=None, count=None):
        self.data = data
        self.count = count


def get_supabase() -> SupabaseDB:
    """Client service_role — opérations admin, bypass RLS."""
    if not SUPABASE_URL or "xxxx" in SUPABASE_URL:
        raise RuntimeError("Supabase non configuré. Remplis SUPABASE_URL et SUPABASE_KEY dans .env")
    return SupabaseDB(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def get_supabase_for_user(user_token: str) -> SupabaseDB:
    """Client anon + JWT utilisateur — RLS actif."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("Supabase non configuré. Remplis SUPABASE_URL et SUPABASE_KEY dans .env")
    db = SupabaseDB(SUPABASE_URL, SUPABASE_KEY)
    db.headers["Authorization"] = f"Bearer {user_token}"
    return db
