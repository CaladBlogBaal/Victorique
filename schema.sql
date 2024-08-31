
CREATE TABLE IF NOT EXISTS guilds (
    guild_id bigint PRIMARY KEY,
    prefix text,
    allow_default boolean NOT NULL,
    replace_twitter_links boolean NOT NULL,
    nsfw_channel bigint
);

CREATE TABLE IF NOT EXISTS users (
    user_id bigint PRIMARY KEY,
    name text NOT NULL,
    credits real NOT NULL,
    daily_cooldown timestamp
);

CREATE TABLE IF NOT EXISTS cursed_user (
    curse_id smallserial PRIMARY KEY,
    user_id bigint REFERENCES users (user_id),
    curse_at bigint REFERENCES guilds (guild_id),
    curse_cooldown timestamp,
    curse_ends_at timestamp,
    curse_name varchar(32)

);

CREATE TABLE IF NOT EXISTS user_tag_usage (
    id SERIAL PRIMARY KEY,
    guild_id bigint REFERENCES guilds (guild_id),
    user_id bigint REFERENCES users (user_id),
    uses smallint default 0
);

CREATE TABLE IF NOT EXISTS cursed_event (
    id SERIAL PRIMARY KEY,
    cursed_by_user_id bigint REFERENCES users (user_id),
    cursed_user_id bigint REFERENCES users (user_id),
    curse_at bigint REFERENCES guilds (guild_id),
    curse_success boolean,
    curse_length interval
);

CREATE UNIQUE INDEX IF NOT EXISTS user_tag_usage_uniq_idx ON user_tag_usage (user_id, guild_id);
CREATE UNIQUE INDEX IF NOT EXISTS cursed_user_uniq_idx ON cursed_user (user_id, curse_at);

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

CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS tsm_system_rows;
CREATE INDEX IF NOT EXISTS tags_name_trgm_idx ON tags USING GIN (tag_name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS tags_name_lower_idx ON tags (LOWER(tag_name));
CREATE UNIQUE INDEX IF NOT EXISTS tags_uniq_idx ON tags (tag_name, guild_id);

CREATE TABLE IF NOT EXISTS fish_bait (
    bait_id smallint PRIMARY KEY,
    bait_name text UNIQUE NOT NULL,
    bait_emote text UNIQUE NOT NULL,
    price float NOT NULL
);

/* C_BAIT = PartialEmoji(animated=False, name="Food1", id=603902930541608960)
R_BAIT = PartialEmoji(animated=False, name="Food2", id=603902989068926976)
E_BAIT = PartialEmoji(animated=False, name="Food5", id=603903148683427840)
# Food5:603903148683427840
SL_BAIT = PartialEmoji(animated=False, name="Food3", id=605394612877656094) */

INSERT INTO fish_bait (bait_id, bait_name, bait_emote, price) VALUES
(1, 'Oxy-cola (common bait)', '<:Food1:603902930541608960>', 75) ON CONFLICT DO NOTHING;

INSERT INTO fish_bait (bait_id, bait_name, bait_emote, price) VALUES
(2, 'Secret-coolant (rare bait)', '<:Food2:603902989068926976>', 100) ON CONFLICT DO NOTHING;

INSERT INTO fish_bait (bait_id, bait_name, bait_emote, price) VALUES
(3, 'Royal-gourmet (elite bait)', '<:Food5:603903148683427840>', 130) ON CONFLICT DO NOTHING;

INSERT INTO fish_bait (bait_id, bait_name, bait_emote, price) VALUES
(4, 'Wisdom-cube (super bait)', '<:Food3:605394612877656094>', 150) ON CONFLICT DO NOTHING;


CREATE TABLE IF NOT EXISTS fish_rarity (
    rarity_id smallint PRIMARY KEY,
    rarity_name text UNIQUE NOT NULL
);

INSERT INTO fish_rarity (rarity_id, rarity_name) VALUES
(1, 'Common') ON CONFLICT DO NOTHING;

INSERT INTO fish_rarity (rarity_id, rarity_name) VALUES
(2, 'Rare') ON CONFLICT DO NOTHING;

INSERT INTO fish_rarity (rarity_id, rarity_name) VALUES
(3, 'Elite') ON CONFLICT DO NOTHING;

INSERT INTO fish_rarity (rarity_id, rarity_name) VALUES
(4, 'Super Rare') ON CONFLICT DO NOTHING;

INSERT INTO fish_rarity (rarity_id, rarity_name) VALUES
(5, 'Legendary') ON CONFLICT DO NOTHING;


CREATE TABLE IF NOT EXISTS fish (
    fish_id SMALLSERIAL PRIMARY KEY,
    fish_name text UNIQUE NOT NULL,
    rarity_id smallint REFERENCES fish_rarity (rarity_id)
);

CREATE TABLE IF NOT EXISTS fish_users (
    user_id bigint REFERENCES users (user_id) ON DELETE CASCADE,
    PRIMARY KEY (user_id)
);

CREATE TABLE IF NOT EXISTS fish_user_inventory (
    user_id bigint REFERENCES fish_users (user_id),
    bait_id smallint REFERENCES fish_bait (bait_id),
    amount int,
    constraint amount_none_negative check (amount>= 0),
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
    CREATE TYPE question_type AS ENUM ('multiple choice', 'True or False');
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
