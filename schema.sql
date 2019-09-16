
CREATE TABLE IF NOT EXISTS guilds (
    guild_id bigint PRIMARY KEY,
    prefix text,
    allow_default boolean NOT NULL,
    nsfw_channel bigint
);

CREATE TABLE IF NOT EXISTS users (
    user_id bigint PRIMARY KEY,
    name text NOT NULL,
    credits real NOT NULL,
    daily_cooldown timestamp
);

CREATE TABLE IF NOT EXISTS tags (
    tag_id SERIAL PRIMARY KEY,
    guild_id bigint REFERENCES guilds (guild_id) ON DELETE CASCADE,
    user_id bigint REFERENCES users (user_id) ON DELETE CASCADE,
    tag_name text,
    content text,
    created_at timestamp
);

CREATE INDEX IF NOT EXISTS tags_name_trgm_idx ON tags USING GIN (tag_name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS tags_name_lower_idx ON tags (LOWER(tag_name));
CREATE UNIQUE INDEX IF NOT EXISTS tags_uniq_idx ON tags (tag_name, guild_id);

CREATE TABLE IF NOT EXISTS fish_bait (
    bait_id smallint PRIMARY KEY,
    bait_name text UNIQUE NOT NULL,
    bait_emote text UNIQUE NOT NULL,
    price float NOT NULL
);

INSERT INTO fish_bait (bait_id, bait_name, bait_emote, price) VALUES
(1, 'Oxy-cola (common bait)', '<:Food1:603902930541608960>', 10) ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS fish (
    fish_id SMALLSERIAL PRIMARY KEY,
    fish_name text UNIQUE NOT NULL,
    bait_id smallint REFERENCES fish_bait (bait_id)
);

CREATE TABLE IF NOT EXISTS fish_users (
    user_id bigint REFERENCES users (user_id) ON DELETE CASCADE,
    PRIMARY KEY (user_id)
);

CREATE TABLE IF NOT EXISTS fish_user_inventory (
    user_id bigint REFERENCES fish_users (user_id),
    bait_id smallint REFERENCES fish_bait (bait_id),
    bait_emote text REFERENCES fish_bait (bait_emote),
    amount int,
    favourites integer[],
    PRIMARY KEY (user_id, bait_id)
);

CREATE TABLE IF NOT EXISTS fish_users_catches (
    user_id bigint REFERENCES fish_users (user_id),
    fish_id smallint REFERENCES fish (fish_id),
    fish_name text REFERENCES fish (fish_name),
    amount int,
    PRIMARY KEY (user_id, fish_id)
);
