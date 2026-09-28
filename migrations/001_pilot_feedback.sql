-- Additive migration. Existing analytics records are untouched.
-- The backend must use the existing server-side service-role key, never an anon key.
CREATE TABLE IF NOT EXISTS public.pilot_feedback (
  request_id uuid PRIMARY KEY,
  created_at timestamptz NOT NULL DEFAULT now(),
  rating text NOT NULL CHECK (rating IN ('up','down')),
  tool text NOT NULL DEFAULT '',
  comment text NOT NULL DEFAULT '',
  participant_id text NOT NULL DEFAULT '',
  country text NOT NULL DEFAULT '',
  language text NOT NULL DEFAULT 'English'
);
ALTER TABLE public.pilot_feedback ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.pilot_feedback FROM anon, authenticated;
GRANT SELECT, INSERT ON public.pilot_feedback TO service_role;
