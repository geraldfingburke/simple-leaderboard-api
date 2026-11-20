CREATE SCHEMA IF NOT EXISTS simple_leaderboard;

CREATE TABLE IF NOT EXISTS simple_leaderboard.users (
    game_id SERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL,
    game_name VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS simple_leaderboard.scores (
    id SERIAL PRIMARY KEY,
    game_id INT NOT NULL REFERENCES simple_leaderboard.users(game_id) ON DELETE CASCADE,
    score INT NOT NULL,
    user_name VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_leaderboard_scores_game_score
    ON simple_leaderboard.scores (game_id, score DESC);
