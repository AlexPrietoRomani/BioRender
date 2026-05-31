# ── Compilación ──
FROM rust:1.91-slim-bookworm AS builder

RUN apt-get update && apt-get install -y pkg-config libssl-dev && rm -rf /var/lib/apt/lists/*

WORKDIR /usr/src/gateway
COPY . .
RUN cargo build --release

# ── Ejecución ──
FROM debian:bookworm-slim

# Instalar libssl3 para TLS, libnss-dns para resolución DNS de Docker y ca-certificates
RUN apt-get update && apt-get install -y \
    ca-certificates \
    libssl3 \
    libnss-dns \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/src/gateway/target/release/gateway /usr/local/bin/gateway

EXPOSE 8080

CMD ["gateway"]
