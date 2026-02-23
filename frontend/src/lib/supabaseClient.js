import { createClient } from "@supabase/supabase-js";

const supabaseUrl = process.env.REACT_APP_SUPABASE_URL || 'https://kpihjwzqtwqlschmtekx.supabase.co'
const supabaseAnonKey = process.env.REACT_APP_SUPABASE_ANON_KEY || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImtwaWhqd3pxdHdxbHNjaG10ZWt4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzA1ODkwODYsImV4cCI6MjA4NjE2NTA4Nn0.91fIJ1ZsG9YHzYlFj2zEG1Zt4L60cJh_Rcq4qOtQDps'

if (!supabaseUrl || !supabaseAnonKey) {
  console.warn(
    "Supabase env vars missing. Set REACT_APP_SUPABASE_URL and REACT_APP_SUPABASE_ANON_KEY in frontend/.env."
  );
}

export const supabase = createClient(
  supabaseUrl || "https://kpihjwzqtwqlschmtekx.supabase.co",
  supabaseAnonKey || "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImtwaWhqd3pxdHdxbHNjaG10ZWt4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzA1ODkwODYsImV4cCI6MjA4NjE2NTA4Nn0.91fIJ1ZsG9YHzYlFj2zEG1Zt4L60cJh_Rcq4qOtQDps"
);
