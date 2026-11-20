import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from psycopg_pool import ConnectionPool

DATABASE_URL = os.getenv("DATABASE_URL", "")
pool: ConnectionPool | None = None


def initialize_database_schema() -> None:
    if not pool:
        return
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE SCHEMA IF NOT EXISTS simple_leaderboard;")
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS simple_leaderboard.users (
                    game_id SERIAL PRIMARY KEY,
                    email VARCHAR(255) NOT NULL,
                    game_name VARCHAR(255) NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS simple_leaderboard.scores (
                    id SERIAL PRIMARY KEY,
                    game_id INT NOT NULL REFERENCES simple_leaderboard.users(game_id) ON DELETE CASCADE,
                    score INT NOT NULL,
                    user_name VARCHAR(255) NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
                """
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_leaderboard_scores_game_score ON simple_leaderboard.scores (game_id, score DESC);"
            )
        conn.commit()


def game_id_exists(game_id: int) -> bool:
    if not pool:
        return False
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT game_id FROM simple_leaderboard.users WHERE game_id = %s;",
                (game_id,),
            )
            return cur.fetchone() is not None


def record_new_user(email: str, game_name: str) -> int:
    assert pool is not None
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT game_id
                FROM simple_leaderboard.users
                WHERE email = %s AND game_name = %s;
                """,
                (email, game_name),
            )
            existing = cur.fetchone()
            if existing:
                return int(existing[0])

            cur.execute(
                """
                INSERT INTO simple_leaderboard.users (email, game_name)
                VALUES (%s, %s)
                RETURNING game_id;
                """,
                (email, game_name),
            )
            created = cur.fetchone()
        conn.commit()
    return int(created[0]) if created else 1


def record_new_score(game_id: int, score: int, user_name: str) -> Response:
    assert pool is not None
    if not game_id_exists(game_id):
        return PlainTextResponse("Invalid GameID")

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO simple_leaderboard.scores (game_id, score, user_name)
                VALUES (%s, %s, %s);
                """,
                (game_id, score, user_name),
            )
        conn.commit()
    return PlainTextResponse("Success")


def get_top_scores(game_id: int, count: int = 10) -> list[dict[str, int | str]]:
    assert pool is not None
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT user_name, score
                FROM simple_leaderboard.scores
                WHERE game_id = %s
                ORDER BY score DESC
                LIMIT %s;
                """,
                (game_id, count),
            )
            rows = cur.fetchall()
    return [{"userName": row[0], "score": row[1]} for row in rows]


def get_user_scores(game_id: int, user_name: str, count: int = 10) -> list[dict[str, int]]:
    assert pool is not None
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT user_name, score
                FROM simple_leaderboard.scores
                WHERE game_id = %s AND user_name = %s
                ORDER BY score DESC
                LIMIT %s;
                """,
                (game_id, user_name, count),
            )
            rows = cur.fetchall()
    return [{row[0]: row[1]} for row in rows]


@asynccontextmanager
async def lifespan(app: FastAPI):
    global pool
    if DATABASE_URL:
        pool = ConnectionPool(conninfo=DATABASE_URL, min_size=1, max_size=10, open=True)
        initialize_database_schema()
    yield
    if pool:
        pool.close()


app = FastAPI(title="Simple Leaderboard API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.api_route("/", methods=["GET", "POST"])
@app.api_route("/apis/simple-leaderboard-api", methods=["GET", "POST"])
@app.api_route("/apis/simple-leaderboard-api/", methods=["GET", "POST"])
@app.api_route("/apis/simple-leaderboard", methods=["GET", "POST"])
@app.api_route("/apis/simple-leaderboard/", methods=["GET", "POST"])
async def handle_leaderboard_request(request: Request) -> Response:
    if not pool:
        return PlainTextResponse("Database connection unavailable", status_code=500)

    query_params = request.query_params
    action = query_params.get("action")
    game_id_param = query_params.get("gameID")
    score_param = query_params.get("score")
    user_name = query_params.get("userName")
    count_param = query_params.get("count")

    if action == "newScore":
        if not (game_id_param and score_param and user_name):
            return PlainTextResponse("Invalid Params")
        try:
            return record_new_score(int(game_id_param), int(score_param), user_name)
        except ValueError:
            return PlainTextResponse("Invalid Params")

    if action == "topScores":
        if not game_id_param:
            return PlainTextResponse("Invalid params")
        try:
            limit = int(count_param) if count_param else 10
            return JSONResponse(get_top_scores(int(game_id_param), limit))
        except ValueError:
            return PlainTextResponse("Invalid params")

    if action == "userScores":
        if not (user_name and game_id_param):
            return PlainTextResponse("Invalid params")
        try:
            limit = int(count_param) if count_param else 10
            return JSONResponse(get_user_scores(int(game_id_param), user_name, limit))
        except ValueError:
            return PlainTextResponse("Invalid params")

    try:
        payload = await request.json()
    except Exception:
        payload = {}

    if isinstance(payload, dict) and payload.get("action") == "addUser":
        email = (payload.get("email") or "").strip()
        game_name = (payload.get("gameName") or "").strip()
        if not (email and game_name):
            return PlainTextResponse("Invalid params")
        return JSONResponse(record_new_user(email, game_name))

    return PlainTextResponse("Invalid params")
