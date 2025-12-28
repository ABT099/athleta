-- ============================================
-- ML Training Jobs Table
-- ============================================

CREATE TYPE ml_job_status_enum AS ENUM ('pending', 'running', 'completed', 'failed');

CREATE TABLE ai_analysis.ml_training_jobs (
    id serial PRIMARY KEY,
    celery_task_id varchar(255),
    athlete_id integer NOT NULL,
    trigger_reason varchar(100) NOT NULL,  -- 'mesocycle_complete', 'staleness', 'session_threshold', 'manual'
    status ml_job_status_enum NOT NULL DEFAULT 'pending',
    created_at timestamp NOT NULL DEFAULT now(),
    started_at timestamp,
    completed_at timestamp,
    training_metrics jsonb,
    error_message text,
    CONSTRAINT ml_training_jobs_athlete_id_fkey 
        FOREIGN KEY (athlete_id) REFERENCES public.athletes(id) ON DELETE CASCADE
);

CREATE INDEX idx_ml_training_jobs_athlete_status 
    ON ai_analysis.ml_training_jobs (athlete_id, status);

CREATE INDEX idx_ml_training_jobs_created_at 
    ON ai_analysis.ml_training_jobs (created_at DESC);

