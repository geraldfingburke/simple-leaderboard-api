import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from psycopg_pool import ConnectionPool

DATABASE_URL = os.getenv("DATABASE_URL", "")
pool: ConnectionPool | None = None


def init_schema() -> None:
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    global pool
    if DATABASE_URL:
        pool = ConnectionPool(conninfo=DATABASE_URL, min_size=1, max_size=10, open=True)
        init_schema()
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
async def leaderboard_endpoint(request: Request) -> Response:
    if not pool:
        return PlainTextResponse("Database connection unavailable", status_code=500)

    qp = request.query_params
    action = qp.get("action")
    game_id_raw = qp.get("gameID")
    score_raw = qp.get("score")
    user_name = qp.get("userName")
    count_raw = qp.get("count")

    # 1. newScore
    if action == "newScore":
        if game_id_raw and score_raw and user_name:
            try:
                game_id = int(game_id_raw)
                score_val = int(score_raw)
            except ValueError:
                return PlainTextResponse("Invalid Params")

            with pool.connection() as conn:
                with conn.cursor() as cur:
                    # Prevents users from adding scores for a gameID that doesn't 'exist'
                    cur.execute(
                        "SELECT game_id FROM simple_leaderboard.users WHERE game_id = %s;",
                        (game_id,),
                    )
                    if not cur.fetchone():
                        return PlainTextResponse("Invalid GameID")

                    cur.execute(
                        """
                        INSERT INTO simple_leaderboard.scores (game_id, score, user_name)
                        VALUES (%s, %s, %s);
                        """,
                        (game_id, score_val, user_name),
                    )
                conn.commit()
            return PlainTextResponse("Success")
        return PlainTextResponse("Invalid Params")

    # 2. topScores
    if action == "topScores":
        if not game_id_raw:
            return PlainTextResponse("Invalid params")
        try:
            game_id = int(game_id_raw)
            limit = int(count_raw) if count_raw else 10
        except ValueError:
            return PlainTextResponse("Invalid params")

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
                    (game_id, limit),
                )
                rows = cur.fetchall()
        return JSONResponse([{"userName": r[0], "score": r[1]} for r in rows])

    # 3. userScores
    if action == "userScores":
        if not user_name or not game_id_raw:
            return PlainTextResponse("Invalid params")
        try:
            game_id = int(game_id_raw)
            limit = int(count_raw) if count_raw else 10
        except ValueError:
            return PlainTextResponse("Invalid params")

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
                    (game_id, user_name, limit),
                )
                rows = cur.fetchall()
        return JSONResponse([{r[0]: r[1]} for r in rows])

    # 4. addUser (POST JSON payload)
    try:
        data = await request.json()
    except Exception:
        data = {}

    if isinstance(data, dict) and data.get("action") == "addUser":
        email = (data.get("email") or "").strip()
        game_name = (data.get("gameName") or "").strip()
        if not email or not game_name:
            return PlainTextResponse("Invalid params")

        with pool.connection() as conn:
            with conn.cursor() as cur:
                # Checks for an existing gameID
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
                    return JSONResponse(existing[0])

                cur.execute(
                    """
                    INSERT INTO simple_leaderboard.users (email, game_name)
                    VALUES (%s, %s)
                    RETURNING game_id;
                    """,
                    (email, game_name),
                )
                new_row = cur.fetchone()
            conn.commit()
        return JSONResponse(new_row[0] if new_row else 1)

    return PlainTextResponse("Invalid params")
