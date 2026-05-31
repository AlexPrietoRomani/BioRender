# ── Compilación ──
FROM rust:1.86-slim AS builder

RUN apt-get update && apt-get install -y pkg-config libssl-dev && rm -rf /var/lib/apt/lists/*

WORKDIR /usr/src/ms_asset_assembly
COPY . .
RUN cargo build --release

# ── Ejecución ──
FROM debian:bookworm-slim

# Instalar TLS/certificados para llamadas salientes si aplica
RUN apt-get update && apt-get install -y ca-certificates && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/src/ms_asset_assembly/target/release/ms_asset_assembly /usr/local/bin/ms_asset_assembly

CMD ["ms_asset_assembly"]
