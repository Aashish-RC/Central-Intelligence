FROM otel/opentelemetry-collector:0.120.0 AS collector

FROM alpine:3.21.3
COPY --from=collector /otelcol /otelcol
USER 10001:10001
ENTRYPOINT ["/otelcol"]
CMD ["--config=/etc/otelcol/config.yaml"]
