-- New Supabase installation. Run once in Supabase SQL Editor as postgres.
-- No browser policies: all commitment access goes through validated FastAPI routes.
BEGIN;
CREATE TABLE public.records (
    id varchar(128) PRIMARY KEY,
    owner_id varchar(36),
    kind varchar(40) NOT NULL,
    version integer NOT NULL DEFAULT 1 CHECK (version > 0),
    data json NOT NULL,
    CONSTRAINT records_owner_scope CHECK (
      (kind = 'ai_budget' AND owner_id IS NULL) OR
      (kind <> 'ai_budget' AND owner_id IS NOT NULL)
    )
);
CREATE INDEX ix_records_owner_kind ON public.records(owner_id, kind);
ALTER TABLE public.records ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.records FROM anon, authenticated;
CREATE TABLE public.kairo_schema_migrations (
    version integer PRIMARY KEY,
    applied_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE public.kairo_schema_migrations ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.kairo_schema_migrations FROM anon, authenticated;
INSERT INTO public.kairo_schema_migrations(version) VALUES (1);
COMMIT;
