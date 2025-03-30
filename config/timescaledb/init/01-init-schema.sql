-- timescaledb/init/01-init-schema.sql
-- Create extensions
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- Create analytics tables
CREATE TABLE IF NOT EXISTS call_metrics (
    time TIMESTAMPTZ NOT NULL,
    session_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    duration_seconds DOUBLE PRECISION,
    status TEXT,
    transcription_count INTEGER,
    intent_count INTEGER,
    silence_ratio DOUBLE PRECISION,
    response_count INTEGER
);

-- Convert to TimescaleDB hypertable for time-series optimization
SELECT create_hypertable('call_metrics', 'time');

-- Speech recognition quality
CREATE TABLE IF NOT EXISTS transcription_quality (
    time TIMESTAMPTZ NOT NULL,
    session_id TEXT NOT NULL,
    streaming_text TEXT,
    final_text TEXT,
    word_error_rate DOUBLE PRECISION,
    character_error_rate DOUBLE PRECISION,
    processing_time_ms INTEGER,
    audio_duration_ms INTEGER
);

SELECT create_hypertable('transcription_quality', 'time');

-- Intent understanding metrics
CREATE TABLE IF NOT EXISTS intent_metrics (
    time TIMESTAMPTZ NOT NULL,
    session_id TEXT NOT NULL,
    text TEXT,
    detected_intent TEXT,
    verification_intent TEXT,
    agreement BOOLEAN,
    confidence DOUBLE PRECISION,
    entity_count INTEGER
);

SELECT create_hypertable('intent_metrics', 'time');

-- ZQS history
CREATE TABLE IF NOT EXISTS zqs_history (
    time TIMESTAMPTZ NOT NULL,
    version TEXT NOT NULL,
    overall_score INTEGER NOT NULL,
    speech_recognition_score INTEGER,
    intent_understanding_score INTEGER,
    response_quality_score INTEGER,
    user_experience_score INTEGER,
    system_performance_score INTEGER
);

SELECT create_hypertable('zqs_history', 'time');

-- Create indexes for faster queries
CREATE INDEX ON call_metrics (session_id, time DESC);
CREATE INDEX ON transcription_quality (session_id, time DESC);
CREATE INDEX ON intent_metrics (session_id, time DESC);
CREATE INDEX ON zqs_history (version, time DESC);