
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

CREATE TABLE IF NOT EXISTS user_tag_usage (
    id SERIAL PRIMARY KEY,
    guild_id bigint REFERENCES guilds (guild_id),
    user_id bigint REFERENCES users (user_id),
    uses smallint default 0
);

CREATE UNIQUE INDEX IF NOT EXISTS user_tag_usage_uniq_idx ON user_tag_usage (user_id, guild_id);

CREATE TABLE IF NOT EXISTS tags (
    tag_id SERIAL PRIMARY KEY,
    guild_id bigint REFERENCES guilds (guild_id),
    user_id bigint REFERENCES users (user_id),
    tag_name text,
    content text,
    nsfw bool,
    created_at timestamp,
    uses smallint default 0
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

CREATE TABLE IF NOT EXISTS category (
    category_id smallint PRIMARY KEY,
    name text
);

INSERT INTO category (category_id, name) VALUES (1, 'General Knowledge') ON CONFLICT DO NOTHING;
INSERT INTO category (category_id, name) VALUES (2, 'Entertainment: Books') ON CONFLICT DO NOTHING;
INSERT INTO category (category_id, name) VALUES (3, 'Entertainment: Film') ON CONFLICT DO NOTHING;
INSERT INTO category (category_id, name) VALUES (4, 'Entertainment: Music') ON CONFLICT DO NOTHING;
INSERT INTO category (category_id, name) VALUES (5, 'Entertainment: Musicals') ON CONFLICT DO NOTHING;
INSERT INTO category (category_id, name) VALUES (6, 'Entertainment: Television') ON CONFLICT DO NOTHING;
INSERT INTO category (category_id, name) VALUES (7, 'Entertainment: Video Games') ON CONFLICT DO NOTHING;
INSERT INTO category (category_id, name) VALUES (8, 'Entertainment: Board Games') ON CONFLICT DO NOTHING;
INSERT INTO category (category_id, name) VALUES (9, 'Science & Nature') ON CONFLICT DO NOTHING;
INSERT INTO category (category_id, name) VALUES (10, 'Science: Computers') ON CONFLICT DO NOTHING;
INSERT INTO category (category_id, name) VALUES (11, 'Science: Mathematics') ON CONFLICT DO NOTHING;
INSERT INTO category (category_id, name) VALUES (12, 'Mythology') ON CONFLICT DO NOTHING;
INSERT INTO category (category_id, name) VALUES (13, 'Sports') ON CONFLICT DO NOTHING;
INSERT INTO category (category_id, name) VALUES (14, 'Geography') ON CONFLICT DO NOTHING;
INSERT INTO category (category_id, name) VALUES (15, 'History') ON CONFLICT DO NOTHING;
INSERT INTO category (category_id, name) VALUES (16, 'Politics') ON CONFLICT DO NOTHING;
INSERT INTO category (category_id, name) VALUES (17, 'Art') ON CONFLICT DO NOTHING;
INSERT INTO category (category_id, name) VALUES (18, 'Celebrities') ON CONFLICT DO NOTHING;
INSERT INTO category (category_id, name) VALUES (19, 'Animals') ON CONFLICT DO NOTHING;
INSERT INTO category (category_id, name) VALUES (20, 'Vehicles') ON CONFLICT DO NOTHING;
INSERT INTO category (category_id, name) VALUES (21, 'Entertainment: Comics') ON CONFLICT DO NOTHING;
INSERT INTO category (category_id, name) VALUES (22, 'Science: Gadgets') ON CONFLICT DO NOTHING;
INSERT INTO category (category_id, name) VALUES (23, 'Entertainment: Japanese Anime & Manga') ON CONFLICT DO NOTHING;
INSERT INTO category (category_id, name) VALUES (24, 'Entertainment: Cartoon & Animations') ON CONFLICT DO NOTHING;


DO $$ BEGIN
    CREATE TYPE  question_type AS ENUM ('multiple choice', 'True or False');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

CREATE TABLE IF NOT EXISTS question (
    question_id SMALLSERIAL PRIMARY KEY,
    category_id smallint REFERENCES category (category_id),
    content text UNIQUE,
    type question_type default 'multiple choice',
    difficulty text

);

CREATE TABLE IF NOT EXISTS answer (
    answer_id SMALLSERIAL,
    question_id smallint REFERENCES question (question_id) ON DELETE CASCADE,
    content text,
    is_correct boolean
);
