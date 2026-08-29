-- PostgreSQL 16 Schema with pgvector and PostGIS
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS postgis;

-- Enum types
CREATE TYPE user_role AS ENUM ('STUDENT', 'STAFF', 'SECURITY_ADMIN');
CREATE TYPE item_type AS ENUM ('LOST', 'FOUND');
CREATE TYPE item_category AS ENUM ('ELECTRONICS', 'WALLETS_CARDS', 'KEYS', 'CLOTHING', 'DOCUMENTS', 'OTHER');
CREATE TYPE item_status AS ENUM ('OPEN', 'MATCH_PENDING', 'HANDOVER_SCHEDULED', 'RESOLVED', 'UNCLAIMED_VAULT');
CREATE TYPE match_status AS ENUM ('HIGH_CONFIDENCE', 'POTENTIAL', 'REJECTED', 'VERIFIED');

-- Users table
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    phone_number VARCHAR(20),
    role user_role DEFAULT 'STUDENT',
    karma_score INTEGER DEFAULT 100,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_role ON users(role);

-- Items table
CREATE TABLE items (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type item_type NOT NULL,
    title VARCHAR(150) NOT NULL,
    description TEXT NOT NULL,
    category item_category NOT NULL,
    campus_zone VARCHAR(100) NOT NULL,
    latitude FLOAT,
    longitude FLOAT,
    incident_time TIMESTAMP WITH TIME ZONE NOT NULL,
    image_urls TEXT[] DEFAULT '{}',
    image_embedding vector(768),
    text_embedding vector(768),
    ocr_tokens TEXT[] DEFAULT '{}',
    is_high_value BOOLEAN DEFAULT FALSE,
    private_details TEXT,
    status item_status DEFAULT 'OPEN',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_items_type ON items(type);
CREATE INDEX idx_items_category ON items(category);
CREATE INDEX idx_items_user_id ON items(user_id);
CREATE INDEX idx_items_status ON items(status);
CREATE INDEX idx_items_image_embedding ON items USING hnsw (image_embedding vector_cosine_ops);
CREATE INDEX idx_items_text_embedding ON items USING hnsw (text_embedding vector_cosine_ops);
CREATE INDEX idx_items_incident_time ON items(incident_time);

-- Matches table
CREATE TABLE matches (
    id SERIAL PRIMARY KEY,
    lost_item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    found_item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    visual_score FLOAT NOT NULL,
    text_score FLOAT NOT NULL,
    category_score FLOAT NOT NULL,
    spatial_decay FLOAT NOT NULL,
    temporal_decay FLOAT NOT NULL,
    ocr_bonus FLOAT NOT NULL,
    total_score FLOAT NOT NULL,
    status match_status NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_matches_lost_item ON matches(lost_item_id);
CREATE INDEX idx_matches_found_item ON matches(found_item_id);
CREATE INDEX idx_matches_total_score ON matches(total_score);
CREATE INDEX idx_matches_status ON matches(status);

-- Claims table
CREATE TABLE claims (
    id SERIAL PRIMARY KEY,
    match_id INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    claimant_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    challenge_question TEXT NOT NULL,
    claimant_answer TEXT NOT NULL,
    is_challenge_approved BOOLEAN DEFAULT FALSE,
    handshake_qr_token VARCHAR(500),
    handover_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    resolved_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_claims_match_id ON claims(match_id);
CREATE INDEX idx_claims_claimant_id ON claims(claimant_id);
