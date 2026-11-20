import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from psycopg_pool import ConnectionPool

DATABASE_URL = os.getenv("DATABASE_URL", "")
pool: ConnectionPool | None = None

PG_INT32_MIN = -2_147_483_648
PG_INT32_MAX = 2_147_483_647
VARCHAR_MAX_LENGTH = 255


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
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    CONSTRAINT uq_leaderboard_users_email_game_name UNIQUE (email, game_name)
                );
                """
            )
            cur.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_leaderboard_users_email_game_name ON simple_leaderboard.users (email, game_name);"
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


def record_new_user(email: str, game_name: str) -> str:
    assert pool is not None
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO simple_leaderboard.users (email, game_name)
                VALUES (%s, %s)
                ON CONFLICT (email, game_name)
                DO UPDATE SET email = EXCLUDED.email
                RETURNING game_id;
                """,
                (email, game_name),
            )
            row = cur.fetchone()
        conn.commit()
    return str(row[0]) if row else "1"


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


def parse_int32(raw_value: str) -> int:
    parsed = int(raw_value)
    if parsed < PG_INT32_MIN or parsed > PG_INT32_MAX:
        raise ValueError("Integer out of 32-bit signed range")
    return parsed


def parse_positive_count(count_param: str | None, default: int = 10) -> int:
    if not count_param:
        return default
    parsed = parse_int32(count_param)
    if parsed < 1:
        raise ValueError("Count must be positive")
    return parsed


def is_within_varchar_limit(value: str | None, max_length: int = VARCHAR_MAX_LENGTH) -> bool:
    return bool(value) and len(value) <= max_length


def extract_bounded_string(
    payload: dict[str, Any], key: str, max_length: int = VARCHAR_MAX_LENGTH
) -> str | None:
    value = payload.get(key)
    if not isinstance(value, str):
        return None
    trimmed = value.strip()
    if not trimmed or len(trimmed) > max_length:
        return None
    return trimmed


@asynccontextmanager
async def lifespan(app: FastAPI):
    global pool
    if DATABASE_URL:
        pool = ConnectionPool(conninfo=DATABASE_URL, min_size=1, max_size=10, open=True)
        await run_in_threadpool(initialize_database_schema)
    yield
    if pool:
        await run_in_threadpool(pool.close)


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
        if not (game_id_param and score_param and is_within_varchar_limit(user_name)):
            return PlainTextResponse("Invalid Params")
        assert user_name is not None
        try:
            game_id = parse_int32(game_id_param)
            score_value = parse_int32(score_param)
        except ValueError:
            return PlainTextResponse("Invalid Params")
        return await run_in_threadpool(record_new_score, game_id, score_value, user_name)

    if action == "topScores":
        if not game_id_param:
            return PlainTextResponse("Invalid params")
        try:
            game_id = parse_int32(game_id_param)
            limit = parse_positive_count(count_param)
        except ValueError:
            return PlainTextResponse("Invalid params")
        scores = await run_in_threadpool(get_top_scores, game_id, limit)
        return JSONResponse(scores)

    if action == "userScores":
        if not (is_within_varchar_limit(user_name) and game_id_param):
            return PlainTextResponse("Invalid params")
        assert user_name is not None
        try:
            game_id = parse_int32(game_id_param)
            limit = parse_positive_count(count_param)
        except ValueError:
            return PlainTextResponse("Invalid params")
        scores = await run_in_threadpool(get_user_scores, game_id, user_name, limit)
        return JSONResponse(scores)

    try:
        payload = await request.json()
    except Exception:
        payload = {}

    if isinstance(payload, dict) and payload.get("action") == "addUser":
        email = extract_bounded_string(payload, "email")
        game_name = extract_bounded_string(payload, "gameName")
        if not (email and game_name):
            return PlainTextResponse("Invalid params")
        registered_game_id = await run_in_threadpool(record_new_user, email, game_name)
        return JSONResponse(registered_game_id)

    return PlainTextResponse("Invalid params")
