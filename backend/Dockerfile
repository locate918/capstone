# ============================================================================
# Locate918 Rust Backend - Dockerfile
# ============================================================================
# Multi-stage build: compile in a build stage, copy binary to slim runtime.
# This keeps the final image small (~100MB vs ~2GB).

# --- Stage 1: Build ---
FROM rust:1.77-bookworm AS builder

WORKDIR /app

# Copy dependency files first (for Docker layer caching)
COPY Cargo.toml Cargo.lock ./

# Create a dummy main.rs to cache dependency compilation
RUN mkdir src && echo "fn main() {}" > src/main.rs
RUN cargo build --release
RUN rm -rf src

# Copy real source code + migrations
COPY src/ src/
COPY migrations/ migrations/

# Force recompile with real source (touch to invalidate cache)
RUN touch src/main.rs
RUN cargo build --release

# --- Stage 2: Runtime ---
FROM debian:bookworm-slim

# Install SSL certs (needed for Supabase HTTPS calls)
RUN apt-get update && apt-get install -y ca-certificates && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy the compiled binary
COPY --from=builder /app/target/release/locate918-backend .

# Copy migrations (needed at runtime for sqlx::migrate!)
COPY migrations/ migrations/

# Railway sets PORT env var automatically
ENV PORT=3000

EXPOSE $PORT

CMD ["./locate918-backend"]