# ── Compilación ──
FROM rust:1.91-slim-bookworm AS builder

RUN apt-get update && apt-get install -y pkg-config libssl-dev && rm -rf /var/lib/apt/lists/*

WORKDIR /usr/src/gateway
COPY . .
RUN cargo build --release

# ── Ejecución ──
FROM debian:bookworm-slim

# Instalar ca-certificates y libssl3 para TLS saliente
RUN apt-get update && apt-get install -y \
    ca-certificates \
    libssl3 \
    && rm -rf /var/lib/apt/lists/*

# Configurar resolución DNS glibc para que resuelva nombres Docker internos
# debian:bookworm-slim omite /etc/nsswitch.conf, rompiendo getaddrinfo()
RUN echo 'hosts: files dns' > /etc/nsswitch.conf

COPY --from=builder /usr/src/gateway/target/release/gateway /usr/local/bin/gateway

EXPOSE 8080

CMD ["gateway"]
