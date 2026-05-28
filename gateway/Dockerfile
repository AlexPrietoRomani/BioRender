# ── Compilación ──
FROM rust:1.78-slim AS builder

WORKDIR /usr/src/gateway
COPY . .
RUN cargo build --release

# ── Ejecución ──
FROM debian:bookworm-slim

# Instalar TLS/certificados para llamadas salientes si aplica
RUN apt-get update && apt-get install -y ca-certificates && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/src/gateway/target/release/gateway /usr/local/bin/gateway

EXPOSE 8080

CMD ["gateway"]
